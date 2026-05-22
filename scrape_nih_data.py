#!/usr/bin/env python3
"""
NIH ODS 补剂数据抓取脚本
从 https://ods.od.nih.gov/factsheets/list-all/ 抓取补剂数据
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# 基础 URL
BASE_URL = "https://ods.od.nih.gov"
LIST_URL = "https://ods.od.nih.gov/factsheets/list-all/"

# 输出目录
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "nih_data_raw")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_supplement_links():
    """获取所有补剂事实清单的链接"""
    print("正在获取补剂列表...")

    response = requests.get(LIST_URL, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(response.text, 'html.parser')

    links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        # 只获取 Consumer 版本的英文链接，排除西班牙文和其他语言
        if '/factsheets/' in href and '-Consumer' in href and '-DatosEnEspanol' not in href:
            # 排除列表页面和 PDF
            if 'list-all' not in href and '.pdf' not in href:
                full_url = urljoin(BASE_URL, href)
                if full_url not in links:
                    links.append(full_url)

    print(f"找到 {len(links)} 个补剂页面")
    return links


def extract_section_content(soup, target_id):
    """根据章节 ID 提取内容"""
    section = soup.find(id=target_id)
    if not section:
        return ""

    content = []
    current = section.next_sibling

    while current:
        # 如果遇到下一个 h2，停止
        if hasattr(current, 'name') and current.name == 'h2':
            break
        if hasattr(current, 'name') and current.name == 'h3':
            # 包含 h3 小标题
            h3_text = current.get_text(strip=True)
            if h3_text:
                content.append(f"\n  {h3_text}\n")
            # 获取 h3 后面的内容，直到下一个 h3 或 h2
            h3_content = current.next_sibling
            while h3_content:
                if hasattr(h3_content, 'name') and h3_content.name in ['h2', 'h3']:
                    break
                if hasattr(h3_content, 'get_text'):
                    text = h3_content.get_text(strip=True)
                    if text:
                        content.append(text)
                elif isinstance(h3_content, str):
                    text = h3_content.strip()
                    if text:
                        content.append(text)
                h3_content = h3_content.next_sibling if hasattr(h3_content, 'next_sibling') else None
            current = current.next_sibling if hasattr(current, 'next_sibling') else None
            continue
        if hasattr(current, 'get_text'):
            text = current.get_text(strip=True)
            if text:
                content.append(text)
        elif isinstance(current, str):
            text = current.strip()
            if text:
                content.append(text)
        current = current.next_sibling if hasattr(current, 'next_sibling') else None

    return ' '.join(content)


def scrape_supplement_page(url):
    """抓取单个补剂页面的数据"""
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')

        # 提取标题
        title = soup.find('h1')
        supplement_name = title.get_text(strip=True) if title else "Unknown"

        # 提取三个关键部分的内容
        # 1. Recommended Intake (h2 id="h2")
        intake_content = extract_section_content(soup, "h2")

        # 2. Interactions with Medications (h2 id="h12")
        interactions_content = extract_section_content(soup, "h12")

        # 3. Can iron be harmful / Health Risks (h2 id="h11" or similar)
        harmful_content = extract_section_content(soup, "h11")
        if not harmful_content:
            # 尝试其他可能的 ID
            for h2 in soup.find_all('h2'):
                h2_text = h2.get_text(strip=True)
                if 'harmful' in h2_text.lower() or 'risk' in h2_text.lower() or 'excessive' in h2_text.lower():
                    harmful_content = extract_section_content(soup, h2.get('id', ''))
                    break

        return {
            "name": supplement_name,
            "url": url,
            "intake": intake_content,
            "interactions": interactions_content,
            "risks": harmful_content
        }
    except Exception as e:
        print(f"  抓取失败 {url}: {e}")
        return None


def save_to_file(data):
    """将数据保存到文件"""
    # 从名称清理文件名
    name = data["name"]
    # 移除特殊字符
    for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
        name = name.replace(char, '_')
    filename = f"{name}.txt"
    filepath = os.path.join(OUTPUT_DIR, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"=== {data['name']} ===\n")
        f.write(f"来源 URL: {data['url']}\n\n")

        if data["intake"]:
            f.write("--- Intakes and Status (推荐摄入量) ---\n")
            f.write(f"{data['intake']}\n\n")

        if data["interactions"]:
            f.write("--- Interactions with Medications (与药物的相互作用) ---\n")
            f.write(f"{data['interactions']}\n\n")

        if data["risks"]:
            f.write("--- Health Risks from Excessive Intake (过量摄入的健康风险) ---\n")
            f.write(f"{data['risks']}\n\n")

    return filepath


def main():
    print("=" * 60)
    print("NIH ODS 补剂数据抓取工具")
    print("=" * 60)

    # 获取所有补剂链接
    links = get_supplement_links()

    # 抓取每个页面
    results = []
    for i, url in enumerate(links, 1):
        print(f"[{i}/{len(links)}] 正在抓取：{url}")
        data = scrape_supplement_page(url)
        if data:
            filepath = save_to_file(data)
            results.append(data)
            print(f"  已保存到：{filepath}")

        # 避免请求过快，等待一下
        time.sleep(1)

    # 统计结果
    print("\n" + "=" * 60)
    print(f"抓取完成！共抓取 {len(results)} 个补剂数据")
    print(f"数据保存在：{OUTPUT_DIR}")
    print("=" * 60)

    # 列出所有保存的文件
    print("\n保存的文件:")
    for f in sorted(os.listdir(OUTPUT_DIR)):
        filepath = os.path.join(OUTPUT_DIR, f)
        size = os.path.getsize(filepath)
        print(f"  {f} ({size} 字节)")


if __name__ == "__main__":
    main()
