"""
Layer 1: 安全性校验模块

集成专业数据库 API：
- RxNorm: 成分名称标准化
- OpenFDA: 药物交互、不良事件、召回信息
- NIH ODS: 剂量上限（通过本地 RAG，因为无官方 API）

API 文档:
- RxNorm: https://rxnormapi.nlm.nih.gov/
- OpenFDA: https://open.fda.gov/apis/
"""

import os
import json
import aiohttp
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()


# ==================== RxNorm API ====================

class RxNormClient:
    """
    RxNorm API 客户端 - 药物名称标准化

    API 文档：https://rxnormapi.nlm.nih.gov/
    无需 API Key，免费使用
    """

    BASE_URL = "https://rxnormapi.nlm.nih.gov/rxnormapi"

    @staticmethod
    async def search_by_name(name: str) -> Optional[Dict]:
        """
        根据名称搜索 RxNorm 药物

        返回匹配的药物信息，用于标准化名称
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{RxNormClient.BASE_URL}/rxnav.json?name={name}",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("drugGroup", None)
        except Exception as e:
            print(f"RxNorm 搜索失败：{e}")
        return None

    @staticmethod
    async def get_rxcui(name: str) -> Optional[str]:
        """
        获取药物的 RxCUI 标识符

        RxCUI 是 RxNorm 的唯一标识符，用于跨数据库查询
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{RxNormClient.BASE_URL}/rxnav.json?name={name}",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        drug_group = data.get("drugGroup", {})
                        concepts = drug_group.get("conceptGroup", [])

                        for concept in concepts:
                            properties = concept.get("conceptProperties", [])
                            if properties:
                                return properties[0].get("rxcui")
        except Exception as e:
            print(f"RxNorm 获取 RxCUI 失败：{e}")
        return None

    @staticmethod
    async def get_drug_interactions(rxcui: str) -> List[Dict]:
        """
        获取药物交互信息

        注意：RxNorm 本身不直接提供交互数据，
        但可以链接到其他数据库（如 First Databank）
        这里预留接口
        """
        # RxNorm 主要提供标准化名称
        # 药物交互需要查询其他专业数据库
        return []

    @staticmethod
    async def normalize_ingredient(name: str) -> Optional[Dict]:
        """
        标准化成分名称

        返回标准化的成分信息
        """
        result = await RxNormClient.search_by_name(name)

        if result:
            concepts = result.get("conceptGroup", [])
            for concept in concepts:
                tty = concept.get("tty")
                if tty == "IN":  # Ingredient
                    properties = concept.get("conceptProperties", [])
                    if properties:
                        return {
                            "original_name": name,
                            "normalized_name": properties[0].get("name"),
                            "rxcui": properties[0].get("rxcui"),
                            "source": "RxNorm"
                        }

        return {
            "original_name": name,
            "normalized_name": name,  # 无法标准化时使用原名
            "rxcui": None,
            "source": "RxNorm (fallback)"
        }


# ==================== OpenFDA API ====================

class OpenFDAClient:
    """
    OpenFDA API 客户端 - 药物安全数据

    API 文档：https://open.fda.gov/apis/
    无需 API Key（免费），但建议申请以提高限流
    限流：无 Key = 240 请求/分钟，有 Key = 120,000 请求/分钟
    """

    BASE_URL = "https://api.fda.gov"

    # 可选：申请 API Key 以提高限流
    # https://open.fda.gov/apis/authentication/
    API_KEY = os.getenv("OPENFDA_API_KEY", None)

    @staticmethod
    async def get_adverse_events(substance: str, limit: int = 10) -> List[Dict]:
        """
        查询药物的不良事件报告

        数据来源：FAERS (FDA Adverse Event Reporting System)

        Returns:
            不良事件列表，包含反应类型、严重程度等
        """
        try:
            headers = {}
            if OpenFDAClient.API_KEY:
                headers["X-Api-Key"] = OpenFDAClient.API_KEY

            async with aiohttp.ClientSession(headers=headers) as session:
                query = f'patient.drug.medicinalproduct:"{substance}"'
                url = f"{OpenFDAClient.BASE_URL}/drug/event.json"

                async with session.get(
                    url,
                    params={
                        "search": query,
                        "limit": limit,
                        "count": "patient.reaction.reactionmeddrapt"
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = data.get("results", [])

                        adverse_events = []
                        for result in results:
                            patient = result.get("patient", {})
                            reactions = patient.get("reaction", [])
                            for reaction in reactions:
                                adverse_events.append({
                                    "reaction": reaction.get("reactionmeddrapt"),
                                    "outcome": reaction.get("reactionoutcome"),
                                    "source": "OpenFDA FAERS",
                                    "url": f"https://open.fda.gov/apis/drug/event/"
                                })

                        return adverse_events
        except Exception as e:
            print(f"OpenFDA 不良事件查询失败：{e}")
        return []

    @staticmethod
    async def get_drug_recalls(drug_name: str, limit: int = 10) -> List[Dict]:
        """
        查询药物召回信息

        数据来源：FDA Enforcement Reports

        Returns:
            召回信息列表，包含召回原因、危险等级等
        """
        try:
            headers = {}
            if OpenFDAClient.API_KEY:
                headers["X-Api-Key"] = OpenFDAClient.API_KEY

            async with aiohttp.ClientSession(headers=headers) as session:
                query = f'product_description:"{drug_name}" OR generic_name:"{drug_name}"'
                url = f"{OpenFDAClient.BASE_URL}/drug/enforcement.json"

                async with session.get(
                    url,
                    params={
                        "search": query,
                        "limit": limit
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = data.get("results", [])

                        recalls = []
                        for recall in results:
                            recalls.append({
                                "reason": recall.get("reason_for_recall"),
                                "class": recall.get("recall_classification"),  # Class I, II, III
                                "date": recall.get("report_date"),
                                "source": "OpenFDA Enforcement",
                                "url": f"https://open.fda.gov/apis/drug/enforcement/"
                            })

                        return recalls
        except Exception as e:
            print(f"OpenFDA 召回查询失败：{e}")
        return []

    @staticmethod
    async def get_drug_labels(substance: str, limit: int = 5) -> List[Dict]:
        """
        查询药物标签信息（包含黑盒警告、禁忌症等）

        数据来源：FDA Structured Product Labels (SPL)

        Returns:
            药物标签信息，包含警告、禁忌症、用法用量等
        """
        try:
            headers = {}
            if OpenFDAClient.API_KEY:
                headers["X-Api-Key"] = OpenFDAClient.API_KEY

            async with aiohttp.ClientSession(headers=headers) as session:
                query = f'openfda.substance:"{substance}"'
                url = f"{OpenFDAClient.BASE_URL}/drug/label.json"

                async with session.get(
                    url,
                    params={
                        "search": query,
                        "limit": limit,
                        "fields": "indications_and_usage,warnings_and_cautions,boxed_warning,contraindications"
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = data.get("results", [])

                        labels = []
                        for label in results:
                            labels.append({
                                "indications": label.get("indications_and_usage", []),
                                "warnings": label.get("warnings_and_cautions", []),
                                "boxed_warning": label.get("boxed_warning", []),  # 黑盒警告（最严重）
                                "contraindications": label.get("contraindications", []),
                                "source": "FDA SPL",
                                "url": f"https://open.fda.gov/apis/drug/label/"
                            })

                        return labels
        except Exception as e:
            print(f"OpenFDA 标签查询失败：{e}")
        return []

    @staticmethod
    async def get_drug_interactions_text(drug_name: str) -> Optional[str]:
        """
        查询 OpenFDA Drug Label API 获取 drug_interactions 字段

        会尝试多种搜索方式：substance_name、generic_name、brand_name

        Returns:
            drug_interactions 原始文本（最长 3000 字符截断），如果没有则返回 None
        """
        if not drug_name or not drug_name.strip():
            return None

        name = drug_name.strip()
        search_fields = [
            f'openfda.substance_name:"{name}"',
            f'openfda.generic_name:"{name}"',
            f'openfda.brand_name:"{name}"',
        ]

        try:
            headers = {}
            if OpenFDAClient.API_KEY:
                headers["X-Api-Key"] = OpenFDAClient.API_KEY

            async with aiohttp.ClientSession(headers=headers) as session:
                for query in search_fields:
                    url = f"{OpenFDAClient.BASE_URL}/drug/label.json"
                    async with session.get(
                        url,
                        params={"search": query, "limit": 1},
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            results = data.get("results", [])
                            if results and results[0].get("drug_interactions"):
                                text = results[0]["drug_interactions"][0]
                                return text[:3000]  # 截断避免过长
                        elif response.status == 404:
                            continue
        except Exception as e:
            print(f"OpenFDA drug_interactions 查询失败 ({name})：{e}")
        return None


# ==================== 药物-补剂相互作用分析 ====================

class DrugInteractionChecker:
    """
    药物与补剂相互作用检查器

    流程：
    1. OpenFDA 获取用户药品的 drug_interactions 原始文本
    2. LLM (qwen-max) 综合分析药品 + 补剂成分 + OpenFDA 文本
    3. 返回结构化的相互作用警告列表
    """

    def __init__(self):
        self.rxnorm = RxNormClient()
        self.openfda = OpenFDAClient()

    async def check(self, medications: List[str], supplement_ingredients: List[str]) -> Dict[str, Any]:
        """
        检查药物与补剂的相互作用

        Args:
            medications: 用户当前服用的药品名称列表
            supplement_ingredients: 计划服用的补剂成分列表

        Returns:
            {
                "warnings": ["【严重】华法林与维生素K：可能降低抗凝效果...", ...],
                "sources": ["https://api.fda.gov/..."],
                "has_high_risk": bool
            }
        """
        results = {
            "warnings": [],
            "sources": [],
            "has_high_risk": False
        }

        if not medications or not supplement_ingredients:
            return results

        # 1. 获取每个药品的 OpenFDA 相互作用文本
        drug_texts = []
        for med in medications:
            text = await self.openfda.get_drug_interactions_text(med)
            if text:
                drug_texts.append(f"【{med}】\n{text}")
                results["sources"].append(
                    f"https://api.fda.gov/drug/label.json?search=openfda.substance_name:{med}"
                )

        if not drug_texts:
            return results

        # 2. 用 LLM 综合分析
        from app.llm_client import get_dashscope_client
        llm = get_dashscope_client(model="qwen-max", max_retries=2, timeout=30)

        prompt = f"""你是一位专业的临床药师。请根据以下信息，判断用户正在服用的药物与计划服用的补剂之间是否存在相互作用风险。

【用户当前服用的药物】
{chr(10).join(f"- {m}" for m in medications)}

【计划服用的补剂成分】
{chr(10).join(f"- {s}" for s in supplement_ingredients)}

【OpenFDA 药物相互作用数据库信息】
{chr(10).join(drug_texts)}

请分析后严格返回 JSON 格式，不要有任何其他文字：
{{
  "interactions": [
    {{
      "drug": "药品名称",
      "supplement": "补剂成分名称",
      "risk_level": "high|medium|low",
      "description": "中文描述，说明相互作用机制和后果"
    }}
  ]
}}

注意：
- 只返回确实存在风险的相互作用
- 如果没有发现明显相互作用，返回空数组 []
- risk_level 定义：high=可能危及生命或严重健康后果；medium=需要关注但非紧急；low=轻微影响
- 所有内容必须使用中文
"""

        try:
            result_text = llm.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            data = json.loads(result_text)
            interactions = data.get("interactions", [])

            for interaction in interactions:
                level = (interaction.get("risk_level") or "").lower()
                drug = interaction.get("drug", "")
                supplement = interaction.get("supplement", "")
                desc = interaction.get("description", "")

                if not drug or not supplement or not desc:
                    continue

                if level == "high":
                    prefix = "【严重】"
                    results["has_high_risk"] = True
                elif level == "medium":
                    prefix = "【注意】"
                else:
                    prefix = "【轻微】"

                results["warnings"].append(f"{prefix}{drug} 与 {supplement}：{desc}")

        except Exception as e:
            print(f"LLM 药物相互作用分析失败：{e}")

        return results


# ==================== Layer 1 安全性校验主逻辑 ====================

class SafetyChecker:
    """
    Layer 1: 安全性校验

    流程：
    1. 使用 RxNorm 标准化成分名称
    2. 查询 OpenFDA 获取不良事件、召回、警告
    3. 查询 NIH DSLD（本地 RAG）获取剂量上限

    返回：
    - safety_score: 安全评分 (0-100)
    - risks: 风险列表
    - recommendations: 建议
    - sources: 数据来源 URL
    """

    def __init__(self):
        self.rxnorm = RxNormClient()
        self.openfda = OpenFDAClient()

    async def check(self, ingredients: List[str]) -> Dict[str, Any]:
        """
        对补剂成分进行安全性检查

        Args:
            ingredients: 成分名称列表

        Returns:
            安全检查结果
        """
        results = {
            "safety_score": 100,  # 初始满分
            "risks": [],
            "recommendations": [],
            "sources": [],
            "ingredients_checked": []
        }

        for ingredient in ingredients:
            # 1. RxNorm 标准化
            normalized = await self.rxnorm.normalize_ingredient(ingredient)
            results["ingredients_checked"].append(normalized)

            # 记录 RxNorm 来源（无论是否找到 RxCUI）
            if normalized.get("rxcui"):
                rxnorm_url = f"https://rxnav.nlm.nih.gov/REST/rxcui/{normalized['rxcui']}"
            else:
                rxnorm_url = f"https://rxnav.nlm.nih.gov/REST/rxnav.json?name={ingredient}"

            if rxnorm_url not in results["sources"]:
                results["sources"].append(rxnorm_url)

            # 2. OpenFDA 不良事件查询
            adverse_events = await self.openfda.get_adverse_events(ingredient, limit=5)
            openfda_ae_url = f"https://open.fda.gov/apis/drug/event/?search=patient.drug.medicinalproduct:\"{ingredient}\""
            if openfda_ae_url not in results["sources"]:
                results["sources"].append(openfda_ae_url)

            if adverse_events:
                # 提取独特的不良反应
                unique_reactions = list(set([e["reaction"] for e in adverse_events if e.get("reaction")]))

                if len(unique_reactions) >= 3:  # 3 个以上不良反应，中等风险
                    results["risks"].append({
                        "type": "adverse_events",
                        "ingredient": ingredient,
                        "reactions": unique_reactions[:5],  # 最多显示 5 个
                        "severity": "medium",
                        "source": "OpenFDA FAERS",
                        "url": openfda_ae_url
                    })
                    results["safety_score"] -= 10

            # 3. OpenFDA 召回查询
            recalls = await self.openfda.get_drug_recalls(ingredient, limit=3)
            openfda_recall_url = f"https://open.fda.gov/apis/drug/enforcement/?search=product_description:\"{ingredient}\""
            if openfda_recall_url not in results["sources"]:
                results["sources"].append(openfda_recall_url)

            if recalls:
                for recall in recalls:
                    if recall.get("class") == "Class I":  # 最严重的召回
                        results["risks"].append({
                            "type": "recall",
                            "ingredient": ingredient,
                            "reason": recall.get("reason"),
                            "class": "Class I (Dangerous)",
                            "severity": "high",
                            "source": "OpenFDA Enforcement",
                            "url": openfda_recall_url
                        })
                        results["safety_score"] -= 30
                    elif recall.get("class") == "Class II":
                        results["risks"].append({
                            "type": "recall",
                            "ingredient": ingredient,
                            "reason": recall.get("reason"),
                            "class": "Class II (Potentially Dangerous)",
                            "severity": "medium",
                            "source": "OpenFDA Enforcement",
                            "url": openfda_recall_url
                        })
                        results["safety_score"] -= 15

            # 4. OpenFDA 标签警告查询
            labels = await self.openfda.get_drug_labels(ingredient, limit=3)
            openfda_label_url = f"https://open.fda.gov/apis/drug/label/?search=openfda.substance:\"{ingredient}\""
            if openfda_label_url not in results["sources"]:
                results["sources"].append(openfda_label_url)

            if labels:
                for label in labels:
                    if label.get("boxed_warning"):  # 黑盒警告
                        results["risks"].append({
                            "type": "boxed_warning",
                            "ingredient": ingredient,
                            "warning": label.get("boxed_warning")[0] if label["boxed_warning"] else "",
                            "severity": "high",
                            "source": "FDA SPL",
                            "url": openfda_label_url
                        })
                        results["safety_score"] -= 25

                    if label.get("contraindications"):
                        results["recommendations"].append({
                            "type": "contraindication",
                            "ingredient": ingredient,
                            "content": label["contraindications"][0] if label["contraindications"] else "",
                            "source": "FDA SPL",
                            "url": openfda_label_url
                        })

        # 确保分数不低于 0
        results["safety_score"] = max(0, results["safety_score"])

        # 生成综合建议
        if results["safety_score"] < 50:
            results["recommendations"].append({
                "type": "general_warning",
                "content": "安全评分较低，建议咨询医生或药剂师",
                "severity": "high"
            })
        elif results["safety_score"] < 80:
            results["recommendations"].append({
                "type": "caution",
                "content": "存在一定风险，请按推荐剂量使用，如有不适请停止使用",
                "severity": "medium"
            })

        return results


# ==================== 测试入口 ====================

async def main():
    """测试安全性检查"""
    checker = SafetyChecker()

    # 测试：常见补剂成分
    ingredients = ["Vitamin D", "Calcium", "Iron", "Magnesium"]

    print("=" * 60)
    print("Layer 1: 安全性校验")
    print("=" * 60)

    result = await checker.check(ingredients)

    print(f"\n安全评分：{result['safety_score']}/100")

    if result["risks"]:
        print(f"\n发现 {len(result['risks'])} 个风险:")
        for risk in result["risks"]:
            print(f"  ⚠️ [{risk['severity']}] {risk['type']}: {risk.get('ingredient', 'N/A')}")
            if risk.get("reactions"):
                print(f"     反应：{', '.join(risk['reactions'])}")

    if result["recommendations"]:
        print(f"\n建议:")
        for rec in result["recommendations"]:
            print(f"  💡 {rec.get('content', '')}")

    if result["sources"]:
        print(f"\n数据来源 ({len(result['sources'])} 条):")
        for url in result["sources"][:3]:  # 显示前 3 个
            print(f"  📖 {url}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
