#!/usr/bin/env python3
"""
NIH ODS 数据清洗脚本
将原始抓取的文本数据转换为结构化的 RAG 知识块格式
"""

import os
import re
import json
from typing import Dict, List, Optional

# 输入输出目录
INPUT_DIR = os.path.join(os.path.dirname(__file__), "nih_data_raw")
OUTPUT_JSON_DIR = os.path.join(os.path.dirname(__file__), "nih_data_processed")
OUTPUT_MARKDOWN_DIR = os.path.join(os.path.dirname(__file__), "nih_data_markdown")

os.makedirs(OUTPUT_JSON_DIR, exist_ok=True)
os.makedirs(OUTPUT_MARKDOWN_DIR, exist_ok=True)

# 补剂类型映射
SUPPLEMENT_TYPES = {
    "Vitamin": "维生素",
    "Calcium": "矿物质",
    "Iron": "矿物质",
    "Zinc": "矿物质",
    "Magnesium": "矿物质",
    "Potassium": "矿物质",
    "Selenium": "矿物质",
    "Copper": "矿物质",
    "Manganese": "矿物质",
    "Molybdenum": "矿物质",
    "Chromium": "矿物质",
    "Iodine": "矿物质",
    "Fluoride": "矿物质",
    "Phosphorus": "矿物质",
    "Omega": "脂肪酸",
    "Probiotics": "益生菌",
    "Biotin": "维生素 B 族",
    "Folate": "维生素 B 族",
    "Niacin": "维生素 B 族",
    "Riboflavin": "维生素 B 族",
    "Thiamin": "维生素 B 族",
    "Ashwagandha": "草本植物",
    "Boron": "微量元素",
    "Carnitine": "氨基酸衍生物",
    "Choline": "维生素样物质",
}


def extract_type_from_name(name: str) -> str:
    """根据名称判断补剂类型"""
    for keyword, type_cn in SUPPLEMENT_TYPES.items():
        if keyword.lower() in name.lower():
            return type_cn
    return "膳食补充剂"


def parse_intake_section(content: str) -> Dict:
    """解析摄入量部分，提取推荐摄入量和上限"""
    result = {
        "recommended_intake": {},
        "upper_limits": {}
    }

    # 提取推荐摄入量表格数据
    intake_pattern = r'(\d+–?\d*|\d+)\s*(?:mcg|mg|IU)'
    matches = re.findall(intake_pattern, content)

    # 提取人群和对应摄入量
    life_stages = [
        ("婴儿 0-6 个月", r"Birth to 6 months|0-6 months"),
        ("婴儿 7-12 个月", r"Infants 7-12 months|7-12 months"),
        ("儿童 1-3 岁", r"Children 1-3 years|1-3 岁"),
        ("儿童 4-8 岁", r"Children 4-8 years|4-8 岁"),
        ("儿童 9-13 岁", r"Children 9-13 years|9-13 岁"),
        ("青少年男性 14-18 岁", r"Teen boys 14-18 years"),
        ("青少年女性 14-18 岁", r"Teen girls 14-18 years"),
        ("成年男性 19-50 岁", r"Adult men 19-50 years"),
        ("成年女性 19-50 岁", r"Adult women 19-50 years"),
        ("成年人 51 岁以上", r"Adults 51 years and older|51 岁以上"),
        ("孕妇", r"Pregnant"),
        ("哺乳期", r"Breastfeeding"),
    ]

    for stage_cn, pattern in life_stages:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            # 尝试提取对应的摄入量
            start = match.end()
            nearby_text = content[start:start+100]
            intake_match = re.search(r'(\d+(?:\.\d+)?)\s*(mcg|mg|IU)', nearby_text, re.IGNORECASE)
            if intake_match:
                value = intake_match.group(1)
                unit = intake_match.group(2).upper()
                result["recommended_intake"][stage_cn] = f"{value} {unit}"

    return result


def parse_drug_interactions(content: str) -> List[Dict]:
    """解析药物相互作用"""
    interactions = []

    # 常见药物相互作用模式
    drug_patterns = [
        (r"levodopa|Sinemet|Stalevo", "左旋多巴（帕金森药物）", "降低药效"),
        (r"levothyroxine|Levoxyl|Synthroid|优甲乐", "左甲状腺素（甲状腺药物）", "降低药效"),
        (r"proton pump inhibitors|lansoprazole|Prevacid|omeprazole|Prilosec", "质子泵抑制剂（胃酸抑制剂）", "降低吸收"),
        (r"tetracycline|四环素", "四环素类抗生素", "相互影响吸收"),
        (r"quinolone|喹诺酮", "喹诺酮类抗生素", "相互影响吸收"),
        (r"bisphosphonate", "双膦酸盐（骨质疏松药物）", "降低吸收"),
        (r"warfarin|Coumadin", "华法林（抗凝药）", "可能影响药效"),
        (r"thiazide|利尿剂", "噻嗪类利尿剂", "可能增加血钙"),
        (r"digoxin|地高辛", "地高辛（心脏药物）", "需谨慎使用"),
        (r"corticosteroid|皮质类固醇", "皮质类固醇", "降低吸收"),
    ]

    for pattern, drug_cn, effect in drug_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            interactions.append({
                "drug": drug_cn,
                "interaction_type": effect,
                "recommendation": "建议间隔 2-4 小时服用"
            })

    return interactions


def parse_health_risks(content: str) -> Dict:
    """解析健康风险信息"""
    risks = {
        "side_effects": [],
        "upper_limit": "",
        "warnings": []
    }

    # 提取副作用
    side_effect_patterns = [
        (r"upset stomach|胃部不适", "胃部不适"),
        (r"constipation|便秘", "便秘"),
        (r"nausea|恶心", "恶心"),
        (r"abdominal pain|腹痛", "腹痛"),
        (r"diarrhea|腹泻", "腹泻"),
        (r"kidney stones|肾结石", "肾结石"),
        (r"kidney failure|肾衰竭", "肾衰竭"),
        (r"liver|肝脏", "肝脏损伤"),
        (r"heart|心脏", "心脏问题"),
    ]

    for pattern, symptom_cn in side_effect_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            risks["side_effects"].append(symptom_cn)

    # 提取每日上限
    upper_match = re.search(r"Upper Limit.*?(\d+)\s*(mcg|mg|IU)", content, re.IGNORECASE)
    if upper_match:
        risks["upper_limit"] = f"{upper_match.group(1)} {upper_match.group(2).upper()}"

    # 提取警告信息
    warning_keywords = [
        (r"hemochromatosis|血色病", "血色病患者应避免补充"),
        (r"kidney disease|肾脏疾病", "肾病患者需谨慎"),
        (r"heart disease|心脏病", "心脏病患者需谨慎"),
        (r"pregnant|怀孕", "孕妇使用前请咨询医生"),
        (r"children|儿童", "请放置在儿童接触不到的地方"),
    ]

    for pattern, warning_cn in warning_keywords:
        if re.search(pattern, content, re.IGNORECASE):
            risks["warnings"].append(warning_cn)

    return risks


def extract_best_timing(name: str, content: str) -> str:
    """根据补剂类型推荐最佳服用时间"""
    name_lower = name.lower()

    # 基于补剂类型的服用时间建议
    timing_rules = {
        "vitamin d": "随餐服用（脂溶性，需要脂肪帮助吸收）",
        "vitamin a": "随餐服用（脂溶性）",
        "vitamin e": "随餐服用（脂溶性）",
        "vitamin k": "随餐服用（脂溶性）",
        "calcium": "随餐服用或睡前服用（碳酸钙需要胃酸，柠檬酸钙可随时服用）",
        "iron": "空腹服用（饭前 1 小时或饭后 2 小时），搭配维生素 C 可增强吸收",
        "magnesium": "随餐服用以减少胃部不适，或睡前服用有助睡眠",
        "zinc": "随餐服用以减少胃部刺激，避免空腹",
        "b12": "空腹服用（早餐前 30 分钟），可提升能量",
        "b-complex": "随早餐服用（可能提升能量，避免晚上服用）",
        "vitamin c": "随餐或空腹均可，分次服用吸收更好",
        "omega": "随餐服用（减少鱼腥味反胃，提高吸收）",
        "probiotics": "饭前 30 分钟或随餐服用（避免胃酸过高）",
        "ashwagandha": "随餐服用，或睡前服用帮助放松",
        "coq10": "随餐服用（脂溶性）",
        "melatonin": "睡前 30-60 分钟服用",
    }

    for keyword, timing in timing_rules.items():
        if keyword in name_lower:
            return timing

    return "建议随餐服用或遵医嘱"


def extract_synergistic(name: str) -> List[str]:
    """提取协同补剂（促进吸收）"""
    name_lower = name.lower()

    synergistic_map = {
        "vitamin d": ["维生素 K2", "钙", "镁"],
        "calcium": ["维生素 D3", "维生素 K2", "镁"],
        "iron": ["维生素 C", "维生素 B12", "叶酸"],
        "magnesium": ["维生素 D3", "钙", "维生素 B6"],
        "zinc": ["铜（少量）", "维生素 B6"],
        "vitamin c": ["铁", "维生素 E"],
        "vitamin e": ["维生素 C", "硒"],
        "vitamin k": ["维生素 D3", "钙"],
        "omega": ["维生素 E（防止氧化）"],
        "b12": ["叶酸", "维生素 B6"],
    }

    for keyword, partners in synergistic_map.items():
        if keyword in name_lower:
            return partners

    return []


def extract_conflicting(name: str) -> List[str]:
    """提取冲突补剂（降低吸收）"""
    name_lower = name.lower()

    conflicting_map = {
        "calcium": ["铁", "锌", "镁（高剂量）"],
        "iron": ["钙", "锌", "镁"],
        "zinc": ["铜", "铁"],
        "magnesium": ["钙（高剂量）", "铁"],
        "copper": ["锌"],
        "vitamin c": ["维生素 B12（大剂量时）"],
    }

    for keyword, conflicts in conflicting_map.items():
        if keyword in name_lower:
            return conflicts

    return []


def parse_file(filepath: str) -> Optional[Dict]:
    """解析单个文件并生成结构化数据"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取基本信息
    name_match = re.match(r'=== (.+?) ===', content)
    if not name_match:
        return None

    name = name_match.group(1).strip()

    # 分割不同部分
    sections = {}
    current_section = "header"
    current_content = []

    for line in content.split('\n'):
        if line.startswith('---'):
            if current_content:
                sections[current_section] = '\n'.join(current_content)
            section_match = re.match(r'--- (.+?) ---', line)
            if section_match:
                current_section = section_match.group(1).strip()
                current_content = []
        else:
            current_content.append(line)

    if current_content:
        sections[current_section] = '\n'.join(current_content)

    # 提取 URL
    url_match = re.search(r'来源 URL: (.+)', content)
    url = url_match.group(1).strip() if url_match else ""

    # 构建结构化数据
    data = {
        "name": name,
        "name_en": name,
        "type": extract_type_from_name(name),
        "source_url": url,
        "best_timing": extract_best_timing(name, content),
        "synergistic_supplements": extract_synergistic(name),
        "conflicting_supplements": extract_conflicting(name),
        "drug_interactions": [],
        "side_effects": [],
        "warnings": [],
        "upper_limit": "",
        "raw_content": {
            "intake": sections.get("Intakes and Status (推荐摄入量)", ""),
            "interactions": sections.get("Interactions with Medications (与药物的相互作用)", ""),
            "risks": sections.get("Health Risks from Excessive Intake (过量摄入的健康风险)", "")
        }
    }

    # 解析药物相互作用
    if data["raw_content"]["interactions"]:
        data["drug_interactions"] = parse_drug_interactions(data["raw_content"]["interactions"])

    # 解析健康风险
    if data["raw_content"]["risks"]:
        risks = parse_health_risks(data["raw_content"]["risks"])
        data["side_effects"] = risks["side_effects"]
        data["upper_limit"] = risks["upper_limit"]
        data["warnings"] = risks["warnings"]

    return data


def generate_markdown(data: Dict) -> str:
    """生成 Markdown 格式的知识块"""
    md = f"# [{data['type']}]: {data['name']}\n\n"

    md += f"- **类型**: {data['type']}\n"
    md += f"- **最佳服用时间**: {data['best_timing']}\n"

    if data['drug_interactions']:
        drugs = [d['drug'] for d in data['drug_interactions']]
        md += f"- **绝对禁忌药物**: {'、'.join(drugs)}。若必须服用，需间隔至少 2-4 小时。\n"

    if data['conflicting_supplements']:
        md += f"- **冲突补剂（降低吸收）**: {'、'.join(data['conflicting_supplements'])}。禁止同服，需间隔 2 小时以上。\n"

    if data['synergistic_supplements']:
        md += f"- **协同补剂（促进吸收）**: {'、'.join(data['synergistic_supplements'])}。建议同服。\n"

    if data['side_effects']:
        md += f"- **副作用警告**: {'、'.join(data['side_effects'])}。\n"

    if data['upper_limit']:
        md += f"- **每日上限**: {data['upper_limit']}\n"

    if data['warnings']:
        md += f"- **特殊警告**: {'、'.join(data['warnings'])}\n"

    md += f"\n---\n*数据来源：{data['source_url']}*\n"

    return md


def main():
    print("=" * 60)
    print("NIH ODS 数据清洗和转换工具")
    print("=" * 60)

    # 获取所有输入文件
    input_files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.txt')]

    print(f"找到 {len(input_files)} 个文件待处理...\n")

    all_data = []
    processed_count = 0

    for filename in input_files:
        filepath = os.path.join(INPUT_DIR, filename)
        print(f"正在处理：{filename}")

        data = parse_file(filepath)
        if data:
            all_data.append(data)
            processed_count += 1

            # 保存 JSON 文件
            json_filename = filename.replace('.txt', '.json')
            json_path = os.path.join(OUTPUT_JSON_DIR, json_filename)
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # 保存 Markdown 文件
            md_filename = filename.replace('.txt', '.md')
            md_path = os.path.join(OUTPUT_MARKDOWN_DIR, md_filename)
            md_content = generate_markdown(data)
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)

            print(f"  ✓ 已生成 JSON 和 Markdown")

    # 创建汇总文件
    print("\n正在创建汇总文件...")

    # JSON 汇总
    all_json_path = os.path.join(OUTPUT_JSON_DIR, "all_supplements.json")
    with open(all_json_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    # Markdown 汇总
    all_md_path = os.path.join(OUTPUT_MARKDOWN_DIR, "all_supplements.md")
    with open(all_md_path, 'w', encoding='utf-8') as f:
        f.write("# NIH 补剂知识库汇总\n\n")
        f.write(f"共收录 {len(all_data)} 种补剂/维生素的详细数据\n\n")
        f.write("---\n\n")
        for data in all_data:
            f.write(generate_markdown(data))
            f.write("\n\n---\n\n")

    print(f"\n{'=' * 60}")
    print(f"处理完成！")
    print(f"  - 成功处理：{processed_count}/{len(input_files)} 个文件")
    print(f"  - JSON 文件保存在：{OUTPUT_JSON_DIR}")
    print(f"  - Markdown 文件保存在：{OUTPUT_MARKDOWN_DIR}")
    print(f"{'=' * 60}")

    # 显示示例
    print("\n📋 示例知识块:")
    if all_data:
        sample = all_data[0]
        print(generate_markdown(sample))


if __name__ == "__main__":
    main()
