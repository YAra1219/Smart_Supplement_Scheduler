import os
import json
import glob
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional
from dotenv import load_dotenv

from app.llm_client import get_dashscope_client, LLMCallError

# 加载环境变量
load_dotenv()

# 初始化 Embedding 客户端（带重试、超时、熔断）
# text-embedding-v3 失败时不降级（无替代模型）
embedding_client = get_dashscope_client(
    model="text-embedding-v3",
    fallback_model=None,  # Embedding 模型无降级
    max_retries=3,
    timeout=30
)


def get_embedding(text: str) -> List[float]:
    """
    使用 text-embedding-v3 生成文本嵌入

    Args:
        text: 输入文本

    Returns:
        嵌入向量

    Raises:
        LLMCallError: 当 Embedding 调用失败时抛出
    """
    try:
        # 使用同步调用，llm_client 内部已处理重试
        # 注意：OpenAI 兼容 API 的 embeddings 接口
        from openai import OpenAI
        api_key = os.getenv("DASHSCOPE_API_KEY")
        client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            timeout=30
        )
        response = client.embeddings.create(
            model="text-embedding-v3",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        raise LLMCallError(f"Embedding 生成失败：{str(e)}", e)


def init_chroma_db() -> chromadb.Collection:
    """
    初始化 ChromaDB 并返回 collection

    Returns:
        ChromaDB collection 对象
    """
    # 获取项目根目录
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    persist_dir = os.path.join(base_dir, "app", "chroma_db")

    # 初始化持久化客户端
    client = chromadb.PersistentClient(path=persist_dir)

    # 获取或创建 collection
    collection = client.get_or_create_collection(
        name="nutrition_rules",
        metadata={"hnsw:space": "cosine"}
    )

    return collection


def load_nih_knowledge() -> List[Dict]:
    """
    从 NIH 处理后的 JSON 文件中加载知识库数据

    Returns:
        知识块列表
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_dir = os.path.join(base_dir, "nih_data_processed")

    knowledge_blocks = []

    # 读取所有 JSON 文件（排除汇总文件）
    json_files = glob.glob(os.path.join(json_dir, "*.json"))

    for json_file in json_files:
        if os.path.basename(json_file) == "all_supplements.json":
            continue

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                knowledge_blocks.append(data)
        except Exception as e:
            print(f"读取文件失败 {json_file}: {e}")

    return knowledge_blocks


def create_chunk_document(block: Dict) -> Dict:
    """
    将知识块转换为可用于向量化的文档格式

    Args:
        block: NIH 知识块数据

    Returns:
        包含多个文档片段的列表
    """
    documents = []
    ids = []
    metadatas = []

    name = block.get("name", "Unknown")
    name_en = block.get("name_en", name)
    supplement_type = block.get("type", "膳食补充剂")

    # 1. 基本信息文档
    basic_text = f"{name}（{name_en}）是一种{supplement_type}。"
    basic_text += f"最佳服用时间：{block.get('best_timing', '遵医嘱')}。"

    if block.get("synergistic_supplements"):
        basic_text += f"协同补剂：{', '.join(block['synergistic_supplements'])}。"

    if block.get("conflicting_supplements"):
        basic_text += f"冲突补剂：{', '.join(block['conflicting_supplements'])}。"

    documents.append(basic_text)
    ids.append(f"{name_en}_basic")
    metadatas.append({
        "supplement": name_en,
        "type": supplement_type,
        "category": "basic_info"
    })

    # 2. 药物相互作用文档
    if block.get("drug_interactions"):
        drug_text = f"{name}的药物相互作用："
        for interaction in block["drug_interactions"]:
            drug_text += f"{interaction['drug']}：{interaction['interaction_type']}。"
            drug_text += f"建议：{interaction['recommendation']}。"

        documents.append(drug_text)
        ids.append(f"{name_en}_drug_interactions")
        metadatas.append({
            "supplement": name_en,
            "type": supplement_type,
            "category": "drug_interaction"
        })

    # 3. 副作用和风险文档
    if block.get("side_effects") or block.get("warnings"):
        risk_text = f"{name}的健康风险："
        if block.get("side_effects"):
            risk_text += f"副作用包括：{', '.join(block['side_effects'])}。"
        if block.get("warnings"):
            risk_text += f"警告：{', '.join(block['warnings'])}。"
        if block.get("upper_limit"):
            risk_text += f"每日上限：{block['upper_limit']}。"

        documents.append(risk_text)
        ids.append(f"{name_en}_health_risks")
        metadatas.append({
            "supplement": name_en,
            "type": supplement_type,
            "category": "health_risk"
        })

    # 4. 协同行业冲突详细文档
    if block.get("synergistic_supplements") or block.get("conflicting_supplements"):
        combo_text = f"{name}的补剂相互作用："
        if block.get("synergistic_supplements"):
            combo_text += f"建议同服的补剂：{', '.join(block['synergistic_supplements'])}。"
        if block.get("conflicting_supplements"):
            combo_text += f"需要间隔服用的补剂：{', '.join(block['conflicting_supplements'])}。"

        documents.append(combo_text)
        ids.append(f"{name_en}_supplement_combinations")
        metadatas.append({
            "supplement": name_en,
            "type": supplement_type,
            "category": "supplement_combination"
        })

    return {
        "documents": documents,
        "ids": ids,
        "metadatas": metadatas
    }


def seed_knowledge_base():
    """
    使用 NIH 权威数据初始化知识库
    """
    collection = init_chroma_db()

    # 如果已有数据，先清空
    if collection.count() > 0:
        print("正在清空旧知识库数据...")
        # 获取所有 ID 并删除
        existing = collection.get(include=[])
        if existing["ids"]:
            collection.delete(ids=existing["ids"])

    # 加载 NIH 知识块
    print("正在加载 NIH 知识块...")
    knowledge_blocks = load_nih_knowledge()

    if not knowledge_blocks:
        print("警告：未找到 NIH 知识块数据，请确保 nih_data_processed 目录存在")
        return

    print(f"找到 {len(knowledge_blocks)} 个补剂知识块")

    # 转换为文档
    all_documents = []
    all_ids = []
    all_metadatas = []

    for block in knowledge_blocks:
        chunk = create_chunk_document(block)
        all_documents.extend(chunk["documents"])
        all_ids.extend(chunk["ids"])
        all_metadatas.extend(chunk["metadatas"])

    print(f"生成 {len(all_documents)} 个知识片段")

    # 批量生成嵌入（带重试）
    print("正在生成向量嵌入...")
    all_embeddings = []
    for i, doc in enumerate(all_documents):
        try:
            embedding = get_embedding(doc)
            all_embeddings.append(embedding)
            if (i + 1) % 10 == 0:
                print(f"  已处理 {i + 1}/{len(all_documents)} 个文档")
        except LLMCallError as e:
            print(f"生成嵌入失败 (ID: {all_ids[i]}): {e}")
            # 使用空向量占位
            all_embeddings.append([0.0] * 1024)

    # 添加到 ChromaDB
    print("正在写入 ChromaDB...")
    collection.add(
        ids=all_ids,
        documents=all_documents,
        embeddings=all_embeddings,
        metadatas=all_metadatas
    )

    print(f"✓ 成功初始化知识库，共 {len(all_documents)} 个知识片段，覆盖 {len(knowledge_blocks)} 种补剂")


def query_knowledge_base(ingredients: List[str], top_k: int = 5) -> List[Dict]:
    """
    根据活性成分查询相关知识

    Args:
        ingredients: 活性成分列表
        top_k: 返回最相关的 K 条规则

    Returns:
        相关规则列表
    """
    collection = init_chroma_db()

    if collection.count() == 0:
        print("警告：知识库为空，请先初始化")
        return []

    # 将成分列表转换为查询文本
    query_text = ", ".join(ingredients)

    # 生成查询嵌入（带重试保护）
    try:
        query_embedding = get_embedding(query_text)
    except LLMCallError as e:
        print(f"查询嵌入生成失败：{e}")
        return []

    # 查询 ChromaDB
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    # 整理结果
    relevant_rules = []
    if results["documents"] and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            relevant_rules.append({
                "rule": doc,
                "supplement": results["metadatas"][0][i].get("supplement", ""),
                "category": results["metadatas"][0][i].get("category", ""),
                "distance": results["distances"][0][i] if results["distances"] else None
            })

    return relevant_rules


def get_supplement_info(name: str) -> Optional[Dict]:
    """
    获取特定补剂的完整信息

    Args:
        name: 补剂名称（中文或英文）

    Returns:
        补剂信息字典，如果未找到则返回 None
    """
    knowledge_blocks = load_nih_knowledge()

    for block in knowledge_blocks:
        if name.lower() in block.get("name_en", "").lower() or name in block.get("name", ""):
            return block

    return None


if __name__ == "__main__":
    # 用于测试和初始化知识库
    print("=" * 60)
    print("NIH 知识库初始化")
    print("=" * 60)
    seed_knowledge_base()

    # 测试查询
    print("\n测试查询：iron, calcium")
    results = query_knowledge_base(["iron", "calcium"], top_k=5)
    for result in results:
        print(f"  [{result['category']}] {result['supplement']}: {result['rule'][:100]}...")
