import os
import json
import asyncio
from typing import List, Dict, AsyncGenerator
from app.models import MedItem, UserRoutine, FinalPlan, ScheduleEntry
from app.llm_client import get_dashscope_client, LLMCallError
from pydantic import TypeAdapter

# 初始化 LLM 客户端（带重试、超时、熔断）
# qwen-max 失败时降级到 qwen-plus
llm_client = get_dashscope_client(
    model="qwen-max",
    fallback_model="qwen-plus",
    max_retries=3,
    timeout=30
)


def _build_messages(medications: List[MedItem], user_routine: UserRoutine, rag_rules: List[Dict]):
    """构建请求消息"""
    # 构建上下文
    med_context = "\n".join([
        f"- {med.name} ({med.type}): 活性成分={med.active_ingredients}, 推荐剂量={med.recommended_dosage}"
        for med in medications
    ])

    routine_context = (
        f"起床时间：{user_routine.wake_up_time}\n"
        f"早餐时间：{user_routine.breakfast_time}\n"
        f"午餐时间：{user_routine.lunch_time}\n"
        f"晚餐时间：{user_routine.dinner_time}\n"
        f"睡觉时间：{user_routine.sleep_time}"
    )

    rules_context = "\n".join([
        f"- {rule['rule']} (补剂：{rule.get('supplement', 'N/A')}, 类别：{rule.get('category', 'N/A')})"
        for rule in rag_rules
    ])

    system_prompt = """你是一个专业的补剂排期助手。你的任务是根据用户提供的补剂信息、
用户作息时间和营养学规则，生成一个无冲突、吸收最大化的每日排期计划。

重要安全规则：
1. 必须严格遵守营养学规则，避免成分冲突
2. 对于有相互作用的补剂，需要建议间隔服用时间
3. 注意提醒用户每日上限和副作用警告

重要语言要求：
- 所有返回内容必须使用中文

重要时间格式要求：
- time 字段必须使用 24 小时制的绝对时间格式（HH:MM），如 "08:00"、"12:30"
- 不要使用相对时间描述（如 "Breakfast"、"随餐"）
- 排期必须按时间顺序排列

请返回 JSON 格式，包含以下字段：
- status: "success" 或 "rejected_due_to_safety"
- rejection_reason: 如果被拒绝，说明原因（中文）
- schedule: 排期列表，每项包含 time（HH:MM 格式）, action（中文）, reasoning（中文）
- warnings: 警告和免责声明列表（中文）"""

    user_prompt = f"""请根据以下信息生成排期计划（所有输出内容请使用中文）：

【补剂列表】
{med_context}

【用户作息时间】
{routine_context}

【营养学规则】
{rules_context}
"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]


async def generate_schedule_stream(
    medications: List[MedItem],
    user_routine: UserRoutine,
    rag_rules: List[Dict]
) -> AsyncGenerator[str, None]:
    """
    流式生成排期计划，逐步返回 JSON 片段

    Args:
        medications: 补剂列表
        user_routine: 用户日常作息时间
        rag_rules: RAG 检索到的规则

    Yields:
        逐步返回的文本片段

    Raises:
        LLMCallError: 当 LLM 调用失败且无法降级时抛出
    """
    messages = _build_messages(medications, user_routine, rag_rules)

    try:
        for chunk_content in llm_client.chat_completion_stream(
            messages=messages,
            response_format={"type": "json_object"}
        ):
            yield chunk_content
            await asyncio.sleep(0.01)  # 小延迟让流式效果更平滑
    except LLMCallError as e:
        raise e


async def generate_schedule(
    medications: List[MedItem],
    user_routine: UserRoutine,
    rag_rules: List[Dict]
) -> FinalPlan:
    """
    使用 qwen-max 生成无冲突的每日排期计划

    Args:
        medications: 补剂列表
        user_routine: 用户日常作息时间
        rag_rules: RAG 检索到的相关规则

    Returns:
        FinalPlan 包含排期计划和警告

    Raises:
        LLMCallError: 当 LLM 调用失败且无法降级时抛出
    """
    messages = _build_messages(medications, user_routine, rag_rules)

    try:
        result_text = llm_client.chat_completion(
            messages=messages,
            response_format={"type": "json_object"}
        )
    except LLMCallError as e:
        raise e

    # 解析响应
    data = json.loads(result_text)

    # 转换为 FinalPlan 模型
    schedule_entries = []
    if data.get("schedule"):
        adapter = TypeAdapter[List[ScheduleEntry]](List[ScheduleEntry])
        schedule_entries = adapter.validate_python(data["schedule"])

    return FinalPlan(
        status=data.get("status", "success"),
        rejection_reason=data.get("rejection_reason"),
        schedule=schedule_entries,
        warnings=data.get("warnings", [])
    )
