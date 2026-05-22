import os
import base64
import json
import re
from typing import List
from app.models import MedItem
from app.llm_client import get_dashscope_client, LLMCallError

# 初始化 LLM 客户端（带重试、超时、熔断）
# qwen-vl-max 失败时降级到 qwen-vl-plus
llm_client = get_dashscope_client(
    model="qwen-vl-max",
    fallback_model="qwen-vl-plus",
    max_retries=3,
    timeout=60  # 图片识别需要更长时间
)


def image_to_base64(image_path: str) -> str:
    """将图片转换为 Base64 编码"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


async def parse_medication_image(image_path: str) -> List[MedItem]:
    """
    使用 qwen-vl-max 解析补剂图片

    Args:
        image_path: 图片文件路径

    Returns:
        MedItem 列表

    Raises:
        LLMCallError: 当 LLM 调用失败且无法降级时抛出
    """
    # 读取图片并转换为 base64
    base64_image = image_to_base64(image_path)

    # 构建提示词
    system_prompt = """你是一个专业的补剂分析助手。请用户上传的补剂瓶子图片，
提取以下信息并以 JSON 格式返回：
1. name: 品牌名或通用名
2. type: 类型（固定返回 "supplement"）
3. active_ingredients: 活性成分列表
4. recommended_dosage: 推荐剂量
5. is_prescription: 是否为处方药（如果检测到处方药标志如 "Rx only"、"Prescription Only" 或药物名称，返回 true）
6. prescription_warning: 如果是处方药，返回警告信息（中文）

重要：请检查图片中是否有以下处方药标志：
- "Rx only" 或 "Rx Only"
- "Prescription Only"
- 处方药编号
- 医生姓名或处方信息
- 已知的处方药名称（如抗生素、降压药、降糖药等）

请只返回 JSON 数组，不要包含任何其他解释。"""

    messages = [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                },
                {
                    "type": "text",
                    "text": "请分析这张图片，提取补剂的详细信息。"
                }
            ]
        }
    ]

    try:
        result_text = llm_client.chat_completion(
            messages=messages,
            response_format={"type": "json_object"}
        )
    except LLMCallError as e:
        # LLM 调用失败，抛出异常
        raise e

    # 处理可能的 JSON 格式
    try:
        # 尝试直接解析
        data = json.loads(result_text)
        if isinstance(data, dict) and "items" in data:
            data = data["items"]
        elif isinstance(data, dict):
            data = [data]
    except json.JSONDecodeError:
        # 如果解析失败，尝试提取 JSON 部分
        json_match = re.search(r'\[.*\]|\{.*\}', result_text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
        else:
            raise ValueError(f"无法解析 LLM 返回的内容：{result_text}")

    # 转换为 MedItem 列表
    from pydantic import TypeAdapter
    adapter = TypeAdapter(List[MedItem])
    return adapter.validate_python(data)
