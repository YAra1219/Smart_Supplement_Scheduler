import os
import tempfile
import json
import base64
from typing import AsyncGenerator
from dotenv import load_dotenv

# 加载.env 文件中的环境变量
load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import shutil

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.models import MedItem, UserRoutine, FinalPlan
from app.vision import parse_medication_image
from app.rag import seed_knowledge_base, query_knowledge_base
from app.schedule_generator import generate_schedule, generate_schedule_stream
from app.tasks import parse_image_task, generate_schedule_task, full_process_task, init_knowledge_base_task
from app.celery_config import celery_app

# 初始化速率限制器
limiter = Limiter(key_func=get_remote_address)

# 初始化 FastAPI 应用
app = FastAPI(
    title="Smart Supplement Scheduler",
    description="AI Agent for managing daily supplements",
    version="0.1.0"
)

# 添加速率限制中间件
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserRoutineRequest(BaseModel):
    wake_up_time: str
    breakfast_time: str
    lunch_time: str
    dinner_time: str
    sleep_time: str
    current_medications: List[str] = Field(default_factory=list, description="用户当前服用的处方药/OTC药品列表")


class ScheduleRequest(BaseModel):
    medications: List[MedItem]
    user_routine: UserRoutineRequest


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化知识库"""
    # 确保环境变量已设置
    if not os.getenv("DASHSCOPE_API_KEY"):
        print("警告：DASHSCOPE_API_KEY 未设置，请确保已设置环境变量")
    # 初始化知识库
    seed_knowledge_base()


@app.get("/")
@limiter.limit("100/minute")
async def root(request: Request):
    return {"message": "Smart Supplement Scheduler API", "status": "running"}


@app.get("/health")
@limiter.limit("100/minute")
async def health_check(request: Request):
    return {"status": "healthy"}


@app.post("/api/init-knowledge-base")
@limiter.limit("5/hour")
async def init_knowledge_base(request: Request):
    """手动初始化/重置知识库"""
    seed_knowledge_base()
    return {"message": "知识库初始化成功"}


@app.post("/api/parse-image", response_model=List[MedItem])
@limiter.limit("10/minute")
async def parse_image(request: Request, image: UploadFile = File(...)):
    """
    解析上传的补剂图片

    Args:
        image: 上传的图片文件

    Returns:
        MedItem 列表

    Raises:
        HTTPException: 文件类型不支持或文件过大时抛出
    """
    # 验证文件类型 - 从文件名扩展名判断，因为 content_type 可能为 None
    allowed_extensions = [".jpg", ".jpeg", ".png", ".webp"]
    filename = image.filename or ""
    file_ext = "." + filename.split(".")[-1].lower() if "." in filename else ""

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型：{file_ext}。请上传 JPEG, PNG 或 WebP 格式的图片"
        )

    # 验证文件大小 (最大 10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    # 读取文件内容以检查大小
    contents = await image.read()
    file_size = len(contents)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大：{file_size / 1024 / 1024:.2f}MB。最大支持 10MB"
        )

    # 验证文件不是空的
    if file_size == 0:
        raise HTTPException(
            status_code=400,
            detail="文件为空，请上传有效的图片"
        )

    # 保存临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
        tmp_file.write(contents)
        tmp_path = tmp_file.name

    try:
        # 解析图片
        medications = await parse_medication_image(tmp_path)
        return medications
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片解析失败：{str(e)}")
    finally:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.post("/api/generate-schedule", response_model=FinalPlan)
@limiter.limit("10/minute")
async def generate_schedule_endpoint(request: Request, schedule_request: ScheduleRequest):
    """
    根据补剂和用户作息生成排期计划

    Args:
        schedule_request: 包含补剂列表和用户作息的请求

    Returns:
        FinalPlan 包含排期计划和警告
    """
    try:
        # 转换 UserRoutine
        user_routine = UserRoutine(
            wake_up_time=schedule_request.user_routine.wake_up_time,
            breakfast_time=schedule_request.user_routine.breakfast_time,
            lunch_time=schedule_request.user_routine.lunch_time,
            dinner_time=schedule_request.user_routine.dinner_time,
            sleep_time=schedule_request.user_routine.sleep_time
        )

        # 从药品中提取活性成分
        all_ingredients = []
        for med in schedule_request.medications:
            all_ingredients.extend(med.active_ingredients)

        # Layer 1: 安全性校验（专业数据库 API）
        from app.safety_checker import SafetyChecker
        checker = SafetyChecker()
        safety_result = await checker.check(all_ingredients)

        # 检查安全评分，过低则拒绝
        if safety_result["safety_score"] < 50:
            return FinalPlan(
                status="rejected_due_to_safety",
                rejection_reason=f"安全检查未通过（评分：{safety_result['safety_score']}/100）。检测到潜在高风险成分，建议咨询医生或药剂师。",
                schedule=[],
                warnings=[risk.get("warning", str(risk)) for risk in safety_result.get("risks", [])],
                safety_score=safety_result["safety_score"],
                data_sources=list(set(safety_result.get("sources", [])))
            )

        # Layer 2: 查询知识库
        rag_rules = query_knowledge_base(all_ingredients, top_k=5)

        # Layer 3: 生成排期计划
        plan = await generate_schedule(
            medications=schedule_request.medications,
            user_routine=user_routine,
            rag_rules=rag_rules
        )

        # 添加安全校验结果
        plan.safety_score = safety_result["safety_score"]
        plan.data_sources = list(set(safety_result.get("sources", [])))

        # 合并警告
        for risk in safety_result.get("risks", []):
            if risk.get("type") == "boxed_warning":
                plan.warnings.insert(0, f"⚠️ FDA 黑盒警告：{risk.get('ingredient')} - {risk.get('warning', '')}")
            elif risk.get("type") == "recall":
                plan.warnings.insert(0, f"⚠️ 召回通知：{risk.get('ingredient')} - {risk.get('reason', '')}")

        # 药物-补剂相互作用检查
        current_medications = schedule_request.user_routine.current_medications or []
        if current_medications:
            from app.safety_checker import DrugInteractionChecker
            interaction_checker = DrugInteractionChecker()
            interaction_result = await interaction_checker.check(
                medications=current_medications,
                supplement_ingredients=all_ingredients
            )
            plan.drug_interactions = interaction_result.get("warnings", [])
            if interaction_result.get("has_high_risk"):
                plan.warnings.insert(0, "⚠️ 检测到高风险药物-补剂相互作用，请务必咨询医生或药剂师")

        return plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成排期失败：{str(e)}")


async def stream_generator(request: ScheduleRequest) -> AsyncGenerator[str, None]:
    """流式生成器，返回 SSE 格式的数据（包含思考过程）"""
    try:
        # 转换 UserRoutine
        user_routine = UserRoutine(
            wake_up_time=request.user_routine.wake_up_time,
            breakfast_time=request.user_routine.breakfast_time,
            lunch_time=request.user_routine.lunch_time,
            dinner_time=request.user_routine.dinner_time,
            sleep_time=request.user_routine.sleep_time
        )

        # 步骤 1: 从药品中提取活性成分
        yield f"data: {json.dumps({'step': 'extract', 'label': '正在识别补剂成分...', 'status': 'running'}, ensure_ascii=False)}\n\n"
        all_ingredients = []
        for med in request.medications:
            all_ingredients.extend(med.active_ingredients)
        yield f"data: {json.dumps({'step': 'extract', 'label': f'已识别 {len(all_ingredients)} 个活性成分', 'status': 'completed'}, ensure_ascii=False)}\n\n"

        # 步骤 2: Layer 1 安全性校验（专业数据库 API）
        yield f"data: {json.dumps({'step': 'safety', 'label': '正在进行安全性校验（RxNorm + OpenFDA）...', 'status': 'running'}, ensure_ascii=False)}\n\n"
        from app.safety_checker import SafetyChecker
        checker = SafetyChecker()
        safety_result = await checker.check(all_ingredients)
        yield f"data: {json.dumps({'step': 'safety', 'label': f'安全评分：{safety_result["safety_score"]}/100', 'status': 'completed', 'safety_score': safety_result["safety_score"]}, ensure_ascii=False)}\n\n"

        # 安全检查未通过
        if safety_result["safety_score"] < 50:
            yield f"data: {json.dumps({'error': f'安全检查未通过（评分：{safety_result["safety_score"]}/100）', 'risks': safety_result.get('risks', [])}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # 步骤 3: 查询知识库
        yield f"data: {json.dumps({'step': 'query', 'label': '正在检索营养学数据库...', 'status': 'running'}, ensure_ascii=False)}\n\n"
        rag_rules = query_knowledge_base(all_ingredients, top_k=5)
        yield f"data: {json.dumps({'step': 'query', 'label': f'已检索 {len(rag_rules)} 条营养学规则', 'status': 'completed'}, ensure_ascii=False)}\n\n"

        # 步骤 4: 生成排期计划
        yield f"data: {json.dumps({'step': 'generate', 'label': 'AI 正在分析成分相互作用...', 'status': 'running'}, ensure_ascii=False)}\n\n"

        # 流式生成排期
        async for chunk in generate_schedule_stream(
            medications=request.medications,
            user_routine=user_routine,
            rag_rules=rag_rules
        ):
            # SSE 格式：data: {...}\n\n
            yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"

        # 步骤完成
        yield f"data: {json.dumps({'step': 'generate', 'label': '排期计划生成完成', 'status': 'completed'}, ensure_ascii=False)}\n\n"

        # 步骤 5: 药物-补剂相互作用检查
        current_medications = request.user_routine.current_medications or []
        if current_medications:
            yield f"data: {json.dumps({'step': 'drug_interactions', 'label': '正在检查药物-补剂相互作用...', 'status': 'running'}, ensure_ascii=False)}\n\n"
            from app.safety_checker import DrugInteractionChecker
            interaction_checker = DrugInteractionChecker()
            interaction_result = await interaction_checker.check(
                medications=current_medications,
                supplement_ingredients=all_ingredients
            )
            warnings = interaction_result.get("warnings", [])
            if warnings:
                yield f"data: {json.dumps({'step': 'drug_interactions', 'label': f'发现 {len(warnings)} 个相互作用警告', 'status': 'completed', 'drug_interactions': warnings}, ensure_ascii=False)}\n\n"
            else:
                yield f"data: {json.dumps({'step': 'drug_interactions', 'label': '未发现明显药物-补剂相互作用', 'status': 'completed'}, ensure_ascii=False)}\n\n"

        # 数据来源
        sources = list(set(safety_result.get("sources", [])))
        if sources:
            yield f"data: {json.dumps({'sources': sources, 'label': f'数据来源 ({len(sources)} 条权威数据库)'}, ensure_ascii=False)}\n\n"

        # 结束标记
        yield "data: [DONE]\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"


@app.post("/api/generate-schedule/stream")
@limiter.limit("10/minute")
async def generate_schedule_stream_endpoint(request: Request, schedule_request: ScheduleRequest):
    """
    流式生成排期计划（Server-Sent Events）

    Args:
        schedule_request: 包含补剂列表和用户作息的请求

    Returns:
        SSE 流，逐步返回生成的内容
    """
    return StreamingResponse(
        stream_generator(schedule_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/full-process", response_model=FinalPlan)
@limiter.limit("10/minute")
async def full_process_endpoint(
    request: Request,
    image: UploadFile = File(...),
    wake_up_time: str = Form(...),
    breakfast_time: str = Form(...),
    lunch_time: str = Form(...),
    dinner_time: str = Form(...),
    sleep_time: str = Form(...),
    current_medications: str = Form("[]")
):
    """
    完整流程：解析图片 + 生成排期

    Args:
        image: 上传的图片文件
        wake_up_time: 起床时间
        breakfast_time: 早餐时间
        lunch_time: 午餐时间
        dinner_time: 晚餐时间
        sleep_time: 睡觉时间
        current_medications: 当前用药 JSON 字符串列表

    Returns:
        FinalPlan 包含排期计划和警告
    """
    # 验证文件类型
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
    if image.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型：{image.content_type}"
        )

    # 保存临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
        shutil.copyfileobj(image.file, tmp_file)
        tmp_path = tmp_file.name

    try:
        # 解析当前用药列表
        try:
            meds_list = json.loads(current_medications) if current_medications else []
        except json.JSONDecodeError:
            meds_list = []

        # 解析图片
        medications = await parse_medication_image(tmp_path)

        # 创建用户作息
        user_routine = UserRoutine(
            wake_up_time=wake_up_time,
            breakfast_time=breakfast_time,
            lunch_time=lunch_time,
            dinner_time=dinner_time,
            sleep_time=sleep_time,
            current_medications=meds_list
        )

        # 从补剂中提取活性成分
        all_ingredients = []
        for med in medications:
            all_ingredients.extend(med.active_ingredients)

        # Layer 1: 安全性校验（专业数据库 API）
        from app.safety_checker import SafetyChecker
        checker = SafetyChecker()
        safety_result = await checker.check(all_ingredients)

        # 安全检查未通过则拒绝
        if safety_result["safety_score"] < 50:
            return FinalPlan(
                status="rejected_due_to_safety",
                rejection_reason=f"安全检查未通过（评分：{safety_result['safety_score']}/100）。检测到潜在高风险成分，建议咨询医生或药剂师。",
                schedule=[],
                warnings=[risk.get("warning", str(risk)) for risk in safety_result.get("risks", [])],
                safety_score=safety_result["safety_score"],
                data_sources=list(set(safety_result.get("sources", [])))
            )

        # Layer 2: 查询知识库
        rag_rules = query_knowledge_base(all_ingredients, top_k=5)

        # Layer 3: 生成排期计划
        plan = await generate_schedule(
            medications=medications,
            user_routine=user_routine,
            rag_rules=rag_rules
        )

        # 添加安全校验结果
        plan.safety_score = safety_result["safety_score"]
        plan.data_sources = list(set(safety_result.get("sources", [])))

        # 合并警告
        for risk in safety_result.get("risks", []):
            if risk.get("type") == "boxed_warning":
                plan.warnings.insert(0, f"⚠️ FDA 黑盒警告：{risk.get('ingredient')} - {risk.get('warning', '')}")
            elif risk.get("type") == "recall":
                plan.warnings.insert(0, f"⚠️ 召回通知：{risk.get('ingredient')} - {risk.get('reason', '')}")

        # 药物-补剂相互作用检查
        if meds_list:
            from app.safety_checker import DrugInteractionChecker
            interaction_checker = DrugInteractionChecker()
            interaction_result = await interaction_checker.check(
                medications=meds_list,
                supplement_ingredients=all_ingredients
            )
            plan.drug_interactions = interaction_result.get("warnings", [])
            if interaction_result.get("has_high_risk"):
                plan.warnings.insert(0, "⚠️ 检测到高风险药物-补剂相互作用，请务必咨询医生或药剂师")

        return plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败：{str(e)}")
    finally:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


# ==================== 异步任务端点 ====================


class AsyncTaskResponse(BaseModel):
    """异步任务响应"""
    task_id: str
    status: str
    message: Optional[str] = None


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    status: str  # PENDING, STARTED, PROGRESS, SUCCESS, FAILURE
    result: Optional[Dict] = None
    error: Optional[str] = None
    progress: Optional[int] = None
    stage: Optional[str] = None


@celery_app.task(bind=True)
def check_task_result(self, task_id: str):
    """检查任务结果（辅助任务）"""
    from celery.result import AsyncResult
    result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None
    }


@app.post("/api/async/parse-image", response_model=AsyncTaskResponse)
@limiter.limit("10/minute")
async def parse_image_async(request: Request, image: UploadFile = File(...)):
    """
    异步解析补剂图片（Celery 任务）

    Args:
        image: 上传的图片文件

    Returns:
        任务 ID，用于后续查询结果
    """
    import base64

    # 验证文件类型
    allowed_extensions = [".jpg", ".jpeg", ".png", ".webp"]
    filename = image.filename or ""
    file_ext = "." + filename.split(".")[-1].lower() if "." in filename else ""

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型：{file_ext}"
        )

    # 验证文件大小
    MAX_FILE_SIZE = 10 * 1024 * 1024
    contents = await image.read()
    file_size = len(contents)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大：{file_size / 1024 / 1024:.2f}MB"
        )

    if file_size == 0:
        raise HTTPException(status_code=400, detail="文件为空")

    # 转换为 Base64 并发送任务
    image_base64 = base64.b64encode(contents).decode("utf-8")

    # 异步执行任务
    task = parse_image_task.delay(image_base64)

    return AsyncTaskResponse(
        task_id=task.id,
        status="submitted",
        message="图片解析任务已提交，请使用 task_id 查询结果"
    )


@app.post("/api/async/generate-schedule", response_model=AsyncTaskResponse)
@limiter.limit("10/minute")
async def generate_schedule_async(request: Request, schedule_request: ScheduleRequest):
    """
    异步生成排期计划（Celery 任务）

    Args:
        schedule_request: 补剂列表和用户作息

    Returns:
        任务 ID
    """
    task = generate_schedule_task.delay(
        medications=[med.model_dump() for med in schedule_request.medications],
        user_routine=schedule_request.user_routine.model_dump()
    )

    return AsyncTaskResponse(
        task_id=task.id,
        status="submitted",
        message="排期生成任务已提交"
    )


@app.post("/api/async/full-process", response_model=AsyncTaskResponse)
@limiter.limit("10/minute")
async def full_process_async(
    request: Request,
    image: UploadFile = File(...),
    wake_up_time: str = Form(...),
    breakfast_time: str = Form(...),
    lunch_time: str = Form(...),
    dinner_time: str = Form(...),
    sleep_time: str = Form(...),
    current_medications: str = Form("[]")
):
    """
    异步完整流程：图片解析 + 排期生成（Celery 任务）

    Args:
        image: 上传的图片文件
        wake_up_time: 起床时间
        breakfast_time: 早餐时间
        lunch_time: 午餐时间
        dinner_time: 晚餐时间
        sleep_time: 睡觉时间
        current_medications: 当前用药 JSON 字符串列表

    Returns:
        任务 ID
    """
    import base64

    # 验证文件
    allowed_extensions = [".jpg", ".jpeg", ".png", ".webp"]
    filename = image.filename or ""
    file_ext = "." + filename.split(".")[-1].lower() if "." in filename else ""

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型：{file_ext}"
        )

    contents = await image.read()
    file_size = len(contents)

    if file_size > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大：{file_size / 1024 / 1024:.2f}MB"
        )

    # 转换为 Base64
    image_base64 = base64.b64encode(contents).decode("utf-8")

    # 解析当前用药列表
    try:
        meds_list = json.loads(current_medications) if current_medications else []
    except json.JSONDecodeError:
        meds_list = []

    # 用户作息
    user_routine = {
        "wake_up_time": wake_up_time,
        "breakfast_time": breakfast_time,
        "lunch_time": lunch_time,
        "dinner_time": dinner_time,
        "sleep_time": sleep_time
    }

    # 异步执行完整流程
    task = full_process_task.delay(
        image_data=image_base64,
        user_routine=user_routine,
        current_medications=meds_list
    )

    return AsyncTaskResponse(
        task_id=task.id,
        status="submitted",
        message="完整流程任务已提交，预计耗时 10-20 秒"
    )


@app.get("/api/task/{task_id}", response_model=TaskStatusResponse)
@limiter.limit("60/minute")
async def get_task_status(request: Request, task_id: str):
    """
    查询任务状态和结果

    Args:
        task_id: 任务 ID

    Returns:
        任务状态和结果
    """
    from celery.result import AsyncResult

    result = AsyncResult(task_id, app=celery_app)

    response = TaskStatusResponse(
        task_id=task_id,
        status=result.status
    )

    if result.status == "SUCCESS":
        response.result = result.result
        response.progress = 100
    elif result.status == "FAILURE":
        response.error = str(result.result)
    elif result.status == "PROGRESS":
        response.result = result.result
        if isinstance(result.result, dict):
            response.progress = result.result.get("progress", 0)
            response.stage = result.result.get("stage", "unknown")
    elif result.status == "PENDING":
        response.progress = 0
    elif result.status == "STARTED":
        response.progress = 10

    return response


@app.post("/api/async/init-knowledge-base", response_model=AsyncTaskResponse)
@limiter.limit("2/hour")
async def init_knowledge_base_async(request: Request):
    """
    异步初始化知识库（Celery 任务）

    Returns:
        任务 ID
    """
    task = init_knowledge_base_task.delay()

    return AsyncTaskResponse(
        task_id=task.id,
        status="submitted",
        message="知识库初始化任务已提交，预计耗时 1-2 分钟"
    )


# ==================== 知识库更新管理端点 ====================


class KnowledgeBaseStatusResponse(BaseModel):
    """知识库状态响应"""
    current_version: Optional[str]
    last_updated: Optional[str]
    next_check: Optional[str]
    total_supplements: int
    update_frequency_days: int
    version_count: int


class KnowledgeBaseHistoryEntry(BaseModel):
    """知识库变更历史条目"""
    version: str
    timestamp: str
    action: str
    supplement_name: str
    details: Dict
    diff_summary: Optional[str] = None


@app.get("/api/knowledge-base/status", response_model=KnowledgeBaseStatusResponse)
@limiter.limit("30/minute")
async def get_knowledge_base_status(request: Request):
    """
    获取知识库状态

    Returns:
        当前版本、最后更新时间、下次检查时间等
    """
    from app.knowledge_base_updater import KnowledgeBaseManager

    kb = KnowledgeBaseManager()
    status = kb.get_status()

    return KnowledgeBaseStatusResponse(**status)


@app.post("/api/knowledge-base/check", response_model=Dict)
@limiter.limit("10/minute")
async def check_knowledge_base_updates(request: Request):
    """
    检查知识库是否有更新

    Returns:
        检查结果，包括是否需要更新、变更内容等
    """
    from app.tasks import check_knowledge_base_updates

    # 同步检查（快速）
    result = check_knowledge_base_updates.delay()

    # 等待结果（最多 30 秒）
    try:
        res = result.get(timeout=30)
        return res
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/knowledge-base/update", response_model=AsyncTaskResponse)
@limiter.limit("2/hour")
async def update_knowledge_base(request: Request, force: bool = False):
    """
    更新知识库（异步任务）

    Args:
        force: 是否强制更新（忽略时间检查）

    Returns:
        任务 ID
    """
    from app.tasks import update_knowledge_base_task

    task = update_knowledge_base_task.delay(force=force)

    return AsyncTaskResponse(
        task_id=task.id,
        status="submitted",
        message="知识库更新任务已提交，预计耗时 2-5 分钟"
    )


@app.get("/api/knowledge-base/history", response_model=List[KnowledgeBaseHistoryEntry])
@limiter.limit("30/minute")
async def get_knowledge_base_history(request: Request, limit: int = 10):
    """
    获取知识库更新历史

    Args:
        limit: 返回最近多少条记录

    Returns:
        变更历史列表
    """
    from app.knowledge_base_updater import KnowledgeBaseManager

    kb = KnowledgeBaseManager()
    history = kb.get_history(limit=limit)

    return [KnowledgeBaseHistoryEntry(**entry) for entry in history]
