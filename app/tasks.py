"""
Celery 异步任务定义
"""

import os
import sys
import asyncio
import tempfile
import shutil
import json
from typing import List, Dict, Optional, Any
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.celery_config import celery_app
from app.knowledge_base_updater import KnowledgeBaseManager
from app.models import MedItem, UserRoutine, FinalPlan, ScheduleEntry
from app.vision import parse_medication_image
from app.rag import query_knowledge_base, seed_knowledge_base
from app.schedule_generator import generate_schedule


@celery_app.task(bind=True, max_retries=2)
def parse_image_task(self, image_data: str) -> Dict[str, Any]:
    """
    异步解析补剂图片

    Args:
        image_data: Base64 编码的图片数据

    Returns:
        任务结果字典
    """
    import base64

    try:
        # 解码 Base64 并保存为临时文件
        image_bytes = base64.b64decode(image_data)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
            tmp_file.write(image_bytes)
            tmp_path = tmp_file.name

        try:
            # 调用图片识别（同步包装 async 函数）
            medications = asyncio.run(parse_medication_image(tmp_path))

            # 转换为字典格式
            result = {
                "status": "success",
                "medications": [
                    {
                        "name": med.name,
                        "type": med.type,
                        "active_ingredients": med.active_ingredients,
                        "recommended_dosage": med.recommended_dosage,
                        "is_prescription": med.is_prescription,
                        "prescription_warning": med.prescription_warning
                    }
                    for med in medications
                ],
                "count": len(medications)
            }

            return result

        finally:
            # 清理临时文件
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    except Exception as e:
        # 重试逻辑
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {
            "status": "error",
            "error": str(e)
        }


@celery_app.task(bind=True, max_retries=2)
def generate_schedule_task(
    self,
    medications: List[Dict],
    user_routine: Dict[str, str]
) -> Dict[str, Any]:
    """
    异步生成排期计划

    Args:
        medications: 补剂列表
        user_routine: 用户作息时间

    Returns:
        任务结果字典
    """
    try:
        # 转换为 Pydantic 模型
        med_items = [
            MedItem(
                name=med["name"],
                type=med["type"],
                active_ingredients=med["active_ingredients"],
                recommended_dosage=med["recommended_dosage"],
                is_prescription=med.get("is_prescription", False),
                prescription_warning=med.get("prescription_warning", "")
            )
            for med in medications
        ]

        routine = UserRoutine(
            wake_up_time=user_routine["wake_up_time"],
            breakfast_time=user_routine["breakfast_time"],
            lunch_time=user_routine["lunch_time"],
            dinner_time=user_routine["dinner_time"],
            sleep_time=user_routine["sleep_time"]
        )

        # 提取所有活性成分
        all_ingredients = []
        for med in med_items:
            all_ingredients.extend(med.active_ingredients)

        # 查询知识库
        rag_rules = query_knowledge_base(all_ingredients, top_k=5)

        # 生成排期（同步包装 async 函数）
        plan = asyncio.run(generate_schedule(
            medications=med_items,
            user_routine=routine,
            rag_rules=rag_rules
        ))

        # 转换为字典格式
        result = {
            "status": "success",
            "plan": {
                "status": plan.status,
                "rejection_reason": plan.rejection_reason,
                "schedule": [
                    {
                        "time": entry.time,
                        "action": entry.action,
                        "reasoning": entry.reasoning
                    }
                    for entry in plan.schedule
                ],
                "warnings": plan.warnings
            },
            "rag_rules_count": len(rag_rules)
        }

        return result

    except Exception as e:
        # 重试逻辑
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {
            "status": "error",
            "error": str(e)
        }


@celery_app.task(bind=True, max_retries=2)
def full_process_task(
    self,
    image_data: str,
    user_routine: Dict[str, str],
    current_medications: List[str] = None
) -> Dict[str, Any]:
    """
    异步完整流程：图片解析 + 排期生成 + 药物相互作用检查

    Args:
        image_data: Base64 编码的图片数据
        user_routine: 用户作息时间
        current_medications: 用户当前服用的处方药/OTC 药品列表

    Returns:
        任务结果字典
    """
    import base64

    try:
        # 更新任务状态：解析图片
        self.update_state(
            state="PROGRESS",
            meta={"stage": "parsing_image", "progress": 10}
        )

        # 解码 Base64 并保存为临时文件
        image_bytes = base64.b64decode(image_data)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
            tmp_file.write(image_bytes)
            tmp_path = tmp_file.name

        try:
            # 步骤 1: 解析图片（同步包装 async 函数）
            medications = asyncio.run(parse_medication_image(tmp_path))

            # 更新状态：已解析
            self.update_state(
                state="PROGRESS",
                meta={
                    "stage": "image_parsed",
                    "progress": 40,
                    "medications_count": len(medications)
                }
            )

            # 转换为 Pydantic 模型（兼容 dict 和 MedItem 对象）
            med_items = []
            for med in medications:
                if isinstance(med, dict):
                    med_items.append(MedItem(
                        name=med.get("name", ""),
                        type=med.get("type", "supplement"),
                        active_ingredients=med.get("active_ingredients", []),
                        recommended_dosage=med.get("recommended_dosage", ""),
                        is_prescription=med.get("is_prescription", False),
                        prescription_warning=med.get("prescription_warning")
                    ))
                else:
                    med_items.append(med)

            routine = UserRoutine(
                wake_up_time=user_routine["wake_up_time"],
                breakfast_time=user_routine["breakfast_time"],
                lunch_time=user_routine["lunch_time"],
                dinner_time=user_routine["dinner_time"],
                sleep_time=user_routine["sleep_time"]
            )

            # 更新状态：生成排期中
            self.update_state(
                state="PROGRESS",
                meta={"stage": "generating_schedule", "progress": 60}
            )

            # 提取所有活性成分
            all_ingredients = []
            for med in med_items:
                all_ingredients.extend(med.active_ingredients)

            # Layer 1: 安全性校验
            self.update_state(
                state="PROGRESS",
                meta={"stage": "safety_check", "progress": 50}
            )
            from app.safety_checker import SafetyChecker
            checker = SafetyChecker()
            safety_result = asyncio.run(checker.check(all_ingredients))

            # 安全检查未通过则拒绝
            if safety_result["safety_score"] < 50:
                return {
                    "status": "rejected_due_to_safety",
                    "rejection_reason": f"安全检查未通过（评分：{safety_result['safety_score']}/100）。检测到潜在高风险成分，建议咨询医生或药剂师。",
                    "schedule": [],
                    "warnings": [risk.get("warning", str(risk)) for risk in safety_result.get("risks", [])],
                    "safety_score": safety_result["safety_score"],
                    "data_sources": list(set(safety_result.get("sources", []))),
                    "drug_interactions": [],
                    "has_high_risk_interaction": False
                }

            # 查询知识库
            self.update_state(
                state="PROGRESS",
                meta={"stage": "querying_knowledge", "progress": 70}
            )
            rag_rules = query_knowledge_base(all_ingredients, top_k=5)

            # 生成排期（同步包装 async 函数）
            self.update_state(
                state="PROGRESS",
                meta={"stage": "generating_plan", "progress": 80}
            )
            plan = asyncio.run(generate_schedule(
                medications=med_items,
                user_routine=routine,
                rag_rules=rag_rules
            ))

            # 完成
            self.update_state(
                state="PROGRESS",
                meta={"stage": "completed", "progress": 100}
            )

            # 药物-补剂相互作用检查
            drug_interactions = []
            has_high_risk = False
            if current_medications:
                self.update_state(
                    state="PROGRESS",
                    meta={"stage": "checking_drug_interactions", "progress": 85}
                )
                from app.safety_checker import DrugInteractionChecker
                interaction_checker = DrugInteractionChecker()
                interaction_result = asyncio.run(interaction_checker.check(
                    medications=current_medications,
                    supplement_ingredients=all_ingredients
                ))
                drug_interactions = interaction_result.get("warnings", [])
                has_high_risk = interaction_result.get("has_high_risk", False)

            # 合并安全校验警告
            merged_warnings = list(plan.warnings)
            for risk in safety_result.get("risks", []):
                if risk.get("type") == "boxed_warning":
                    merged_warnings.insert(0, f"⚠️ FDA 黑盒警告：{risk.get('ingredient')} - {risk.get('warning', '')}")
                elif risk.get("type") == "recall":
                    merged_warnings.insert(0, f"⚠️ 召回通知：{risk.get('ingredient')} - {risk.get('reason', '')}")

            # 转换为与 FinalPlan 一致的扁平字典格式
            result = {
                "status": plan.status,
                "rejection_reason": plan.rejection_reason,
                "schedule": [
                    {
                        "time": entry.time,
                        "action": entry.action,
                        "reasoning": entry.reasoning
                    }
                    for entry in plan.schedule
                ],
                "warnings": merged_warnings,
                "safety_score": safety_result["safety_score"],
                "data_sources": list(set(safety_result.get("sources", []))),
                "drug_interactions": drug_interactions,
                "has_high_risk_interaction": has_high_risk
            }

            return result

        finally:
            # 清理临时文件
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    except Exception as e:
        # 重试逻辑
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=2 ** self.request.retries)

        return {
            "status": "error",
            "error": str(e)
        }


@celery_app.task
def init_knowledge_base_task() -> Dict[str, Any]:
    """
    异步初始化知识库

    Returns:
        任务结果字典
    """
    try:
        seed_knowledge_base()
        return {
            "status": "success",
            "message": "知识库初始化成功"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


@celery_app.task(bind=True, max_retries=1)
def update_knowledge_base_task(self, force: bool = False) -> Dict[str, Any]:
    """
    异步更新知识库（定期执行）

    Args:
        force: 是否强制更新

    Returns:
        任务结果字典
    """
    try:
        kb = KnowledgeBaseManager()
        success, message = kb.update(force=force)

        return {
            "status": "success" if success else "no_update",
            "message": message,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        # 重试逻辑
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60)

        return {
            "status": "error",
            "error": str(e)
        }


@celery_app.task
def check_knowledge_base_updates() -> Dict[str, Any]:
    """
    检查知识库是否有更新

    Returns:
        任务结果字典
    """
    try:
        kb = KnowledgeBaseManager()
        result = kb.check_for_updates()

        return {
            "status": "success",
            "needs_update": result.get("needs_update", False),
            "changes": result.get("changes", {}),
            "last_updated": result.get("last_updated"),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
