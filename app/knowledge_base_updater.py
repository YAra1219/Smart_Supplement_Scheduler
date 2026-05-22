"""
知识库更新管理器

功能：
1. 定期从权威源（NIH ODS）自动更新数据
2. 版本管理 - 记录每个版本的元数据
3. 增量更新 - 只更新有变化的部分
4. 变更日志 - 记录每次更新的内容

使用方式：
    python -m app.knowledge_base_updater --check      # 检查是否有更新
    python -m app.knowledge_base_updater --update     # 执行更新
    python -m app.knowledge_base_updater --history    # 查看更新历史
    python -m app.knowledge_base_updater --status     # 查看当前状态
"""

import os
import sys
import json
import hashlib
import shutil
import tempfile
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import difflib


# ==================== 配置 ====================

# NIH ODS 数据源
NIH_BASE_URL = "https://ods.od.nih.gov"
NIH_LIST_URL = "https://ods.od.nih.gov/factsheets/list-all/"

# 数据目录
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "knowledge_base"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
VERSIONS_DIR = DATA_DIR / "versions"
CHANGELOG_FILE = DATA_DIR / "changelog.json"
METADATA_FILE = DATA_DIR / "metadata.json"

# 确保目录存在
for dir_path in [RAW_DATA_DIR, PROCESSED_DATA_DIR, VERSIONS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)


# ==================== 数据模型 ====================

@dataclass
class SupplementRecord:
    """补剂记录"""
    name: str
    name_en: str
    url: str
    intake: str  # 推荐摄入量
    interactions: str  # 药物相互作用
    risks: str  # 过量风险
    scraped_at: str  # 抓取时间
    content_hash: str  # 内容哈希（用于检测变化）


@dataclass
class VersionInfo:
    """版本信息"""
    version: str
    created_at: str
    supplement_count: int
    changes: Dict[str, Any]
    source_url: str
    notes: str = ""


@dataclass
class ChangeLogEntry:
    """变更日志条目"""
    version: str
    timestamp: str
    action: str  # added, updated, removed, unchanged
    supplement_name: str
    details: Dict[str, Any]
    diff_summary: Optional[str] = None


# ==================== NIH 数据抓取器 ====================

class NIHScraper:
    """NIH ODS 数据抓取器"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; SmartSupplementBot/1.0; +https://github.com/your-repo)"
        })

    def get_supplement_list(self) -> List[Dict[str, str]]:
        """获取所有补剂事实清单的链接"""
        print("正在获取 NIH 补剂列表...")

        try:
            response = self.session.get(NIH_LIST_URL, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            supplements = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                # 只获取 Consumer 版本的英文链接
                if '/factsheets/' in href and '-Consumer' in href and '-DatosEnEspanol' not in href:
                    if 'list-all' not in href and '.pdf' not in href:
                        full_url = urljoin(NIH_BASE_URL, href)
                        # 从 URL 和链接文本提取名称
                        name_text = a.get_text(strip=True)
                        supplements.append({
                            "name": name_text,
                            "url": full_url
                        })

            print(f"找到 {len(supplements)} 个补剂页面")
            return supplements

        except Exception as e:
            print(f"获取补剂列表失败：{e}")
            return []

    def extract_section_content(self, soup: BeautifulSoup, target_id: str) -> str:
        """根据章节 ID 提取内容"""
        section = soup.find(id=target_id)
        if not section:
            return ""

        content = []
        current = section.next_sibling

        while current:
            if hasattr(current, 'name') and current.name == 'h2':
                break
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

    def scrape_supplement(self, url: str) -> Optional[SupplementRecord]:
        """抓取单个补剂页面"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # 提取标题
            title = soup.find('h1')
            full_name = title.get_text(strip=True) if title else "Unknown"

            # 提取英文名（从 URL 推断）
            name_en = url.split('/')[-1].replace('.html', '').split('-')[0]

            # 提取关键章节内容
            intake = self.extract_section_content(soup, "h2")  # Recommended Intake
            interactions = self.extract_section_content(soup, "h12")  # Interactions with Medications
            risks = self.extract_section_content(soup, "h11")  # Health Risks

            # 构建内容哈希（用于检测变化）
            content_string = f"{intake}{interactions}{risks}"
            content_hash = hashlib.md5(content_string.encode('utf-8')).hexdigest()

            return SupplementRecord(
                name=full_name,
                name_en=name_en,
                url=url,
                intake=intake,
                interactions=interactions,
                risks=risks,
                scraped_at=datetime.now().isoformat(),
                content_hash=content_hash
            )

        except Exception as e:
            print(f"  抓取失败 {url}: {e}")
            return None

    def scrape_all(self, delay: float = 0.5) -> List[SupplementRecord]:
        """抓取所有补剂数据"""
        supplements = self.get_supplement_list()
        records = []

        for i, supp in enumerate(supplements, 1):
            print(f"  [{i}/{len(supplements)}] 正在抓取：{supp['name']}")
            record = self.scrape_supplement(supp['url'])
            if record:
                records.append(record)

            # 避免请求过快
            if delay > 0:
                time.sleep(delay)

        return records


# ==================== 知识库管理器 ====================

class KnowledgeBaseManager:
    """知识库管理器"""

    def __init__(self):
        self.scraper = NIHScraper()
        self._ensure_metadata()

    def _ensure_metadata(self):
        """确保元数据文件存在"""
        if not METADATA_FILE.exists():
            self._save_metadata({
                "current_version": None,
                "last_updated": None,
                "total_supplements": 0,
                "next_check": None,
                "update_frequency_days": 30  # 每月检查一次
            })

    def _load_metadata(self) -> Dict:
        """加载元数据"""
        if METADATA_FILE.exists():
            with open(METADATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_metadata(self, metadata: Dict):
        """保存元数据"""
        with open(METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def _load_existing_records(self) -> Dict[str, SupplementRecord]:
        """加载现有记录（按名称索引）"""
        records = {}
        if PROCESSED_DATA_DIR.exists():
            for json_file in PROCESSED_DATA_DIR.glob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        record = SupplementRecord(**data)
                        records[record.name_en] = record
                except Exception as e:
                    print(f"加载记录失败 {json_file}: {e}")
        return records

    def _save_records(self, records: List[SupplementRecord], version: str):
        """保存记录到版本目录和处理后目录"""
        version_dir = VERSIONS_DIR / version
        version_dir.mkdir(parents=True, exist_ok=True)

        # 保存每个记录为 JSON
        for record in records:
            # 保存到版本目录
            version_file = version_dir / f"{record.name_en}.json"
            with open(version_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(record), f, indent=2, ensure_ascii=False)

            # 同步到处理后目录（供 RAG 使用）
            processed_file = PROCESSED_DATA_DIR / f"{record.name_en}.json"
            with open(processed_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(record), f, indent=2, ensure_ascii=False)

    def _compute_diff(self, old_records: Dict[str, SupplementRecord],
                      new_records: List[SupplementRecord]) -> Dict[str, List]:
        """计算差异"""
        changes = {
            "added": [],
            "updated": [],
            "removed": [],
            "unchanged": []
        }

        new_names = set()

        for record in new_records:
            new_names.add(record.name_en)

            if record.name_en not in old_records:
                # 新增
                changes["added"].append({
                    "name": record.name,
                    "name_en": record.name_en,
                    "url": record.url
                })
            else:
                old = old_records[record.name_en]
                if old.content_hash != record.content_hash:
                    # 有变化
                    changes["updated"].append({
                        "name": record.name,
                        "name_en": record.name_en,
                        "url": record.url,
                        "old_hash": old.content_hash,
                        "new_hash": record.content_hash,
                        "diff": self._generate_diff_summary(old, record)
                    })
                else:
                    changes["unchanged"].append(record.name_en)

        # 检查删除的
        for name_en, old in old_records.items():
            if name_en not in new_names:
                changes["removed"].append({
                    "name": old.name,
                    "name_en": name_en,
                    "url": old.url
                })

        return changes

    def _generate_diff_summary(self, old: SupplementRecord, new: SupplementRecord) -> str:
        """生成差异摘要"""
        diffs = []

        # 比较各个字段
        for field in ['intake', 'interactions', 'risks']:
            old_text = getattr(old, field, "")
            new_text = getattr(new, field, "")

            if old_text != new_text:
                # 简单的长度差异
                old_len = len(old_text.split())
                new_len = len(new_text.split())
                diffs.append(f"{field}: {old_len}词 → {new_len}词")

        return "; ".join(diffs) if diffs else "内容有小幅更新"

    def _save_changelog_entry(self, entry: ChangeLogEntry):
        """保存变更日志条目"""
        changelog = []
        if CHANGELOG_FILE.exists():
            with open(CHANGELOG_FILE, 'r', encoding='utf-8') as f:
                changelog = json.load(f)

        changelog.insert(0, asdict(entry))

        # 只保留最近 100 条
        changelog = changelog[:100]

        with open(CHANGELOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(changelog, f, indent=2, ensure_ascii=False)

    def check_for_updates(self) -> Dict[str, Any]:
        """检查是否有可用更新"""
        print("=" * 60)
        print("检查知识库更新")
        print("=" * 60)

        metadata = self._load_metadata()
        last_updated = metadata.get("last_updated")

        if last_updated:
            last_dt = datetime.fromisoformat(last_updated)
            next_check = last_dt + timedelta(days=metadata.get("update_frequency_days", 30))

            if datetime.now() < next_check:
                print(f"✓ 上次更新：{last_dt.strftime('%Y-%m-%d')}")
                print(f"  下次检查：{next_check.strftime('%Y-%m-%d')}")
                print(f"  状态：无需检查（距离上次更新不足 {metadata.get('update_frequency_days', 30)} 天）")
                return {
                    "needs_update": False,
                    "reason": "未到检查时间",
                    "last_updated": last_updated,
                    "next_check": next_check.isoformat()
                }

        print(f"上次更新：{last_updated or '从未'}")
        print("正在抓取 NIH 最新数据...")

        # 抓取最新数据（不保存，只比较）
        new_records = self.scraper.scrape_all(delay=0.2)
        old_records = self._load_existing_records()

        changes = self._compute_diff(old_records, new_records)

        print(f"\n比较结果:")
        print(f"  新增：{len(changes['added'])} 个")
        print(f"  更新：{len(changes['updated'])} 个")
        print(f"  删除：{len(changes['removed'])} 个")
        print(f"  未变：{len(changes['unchanged'])} 个")

        return {
            "needs_update": bool(changes["added"] or changes["updated"] or changes["removed"]),
            "last_updated": last_updated,
            "changes": changes,
            "new_record_count": len(new_records)
        }

    def update(self, force: bool = False) -> Tuple[bool, str]:
        """执行更新"""
        print("=" * 60)
        print("执行知识库更新")
        print("=" * 60)

        metadata = self._load_metadata()

        # 检查是否需要更新
        if not force:
            last_updated = metadata.get("last_updated")
            if last_updated:
                last_dt = datetime.fromisoformat(last_updated)
                next_check = last_dt + timedelta(days=metadata.get("update_frequency_days", 30))
                if datetime.now() < next_check:
                    return False, f"未到检查时间，下次检查：{next_check.strftime('%Y-%m-%d')}"

        # 抓取新数据
        print("\n正在抓取 NIH 最新数据...")
        new_records = self.scraper.scrape_all(delay=0.3)

        if not new_records:
            return False, "抓取失败，未获取到新数据"

        print(f"抓取到 {len(new_records)} 个补剂记录")

        # 加载旧记录并计算差异
        old_records = self._load_existing_records()
        changes = self._compute_diff(old_records, new_records)

        # 如果没有变化
        if not (changes["added"] or changes["updated"] or changes["removed"]):
            print("\n✓ 数据无变化，跳过更新")
            return False, "数据无变化"

        # 生成新版本号
        timestamp = datetime.now().strftime("%Y%m%d")
        version = f"v{timestamp}"

        # 保存新记录
        print(f"\n正在保存版本 {version}...")
        self._save_records(new_records, version)

        # 更新元数据
        metadata["current_version"] = version
        metadata["last_updated"] = datetime.now().isoformat()
        metadata["total_supplements"] = len(new_records)
        metadata["next_check"] = (datetime.now() + timedelta(days=metadata.get("update_frequency_days", 30))).isoformat()
        self._save_metadata(metadata)

        # 记录变更日志
        if changes["added"]:
            for item in changes["added"]:
                self._save_changelog_entry(ChangeLogEntry(
                    version=version,
                    timestamp=datetime.now().isoformat(),
                    action="added",
                    supplement_name=item["name"],
                    details={"name_en": item["name_en"], "url": item["url"]}
                ))

        if changes["updated"]:
            for item in changes["updated"]:
                self._save_changelog_entry(ChangeLogEntry(
                    version=version,
                    timestamp=datetime.now().isoformat(),
                    action="updated",
                    supplement_name=item["name"],
                    details={
                        "name_en": item["name_en"],
                        "url": item["url"],
                        "diff": item["diff"]
                    },
                    diff_summary=item["diff"]
                ))

        if changes["removed"]:
            for item in changes["removed"]:
                self._save_changelog_entry(ChangeLogEntry(
                    version=version,
                    timestamp=datetime.now().isoformat(),
                    action="removed",
                    supplement_name=item["name"],
                    details={"name_en": item["name_en"], "url": item["url"]}
                ))

        # 保存版本信息
        version_info = VersionInfo(
            version=version,
            created_at=datetime.now().isoformat(),
            supplement_count=len(new_records),
            changes=changes,
            source_url=NIH_LIST_URL,
            notes=f"自动更新：新增{len(changes['added'])}, 更新{len(changes['updated'])}, 删除{len(changes['removed'])}"
        )

        version_file = VERSIONS_DIR / f"{version}.json"
        with open(version_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(version_info), f, indent=2, ensure_ascii=False)

        print(f"\n✓ 更新完成!")
        print(f"  版本：{version}")
        print(f"  新增：{len(changes['added'])} 个")
        print(f"  更新：{len(changes['updated'])} 个")
        print(f"  删除：{len(changes['removed'])} 个")

        return True, f"更新完成：{version}"

    def get_history(self, limit: int = 10) -> List[Dict]:
        """获取更新历史"""
        changelog = []
        if CHANGELOG_FILE.exists():
            with open(CHANGELOG_FILE, 'r', encoding='utf-8') as f:
                changelog = json.load(f)
        return changelog[:limit]

    def get_status(self) -> Dict:
        """获取当前状态"""
        metadata = self._load_metadata()

        # 计算版本数量
        version_count = len(list(VERSIONS_DIR.glob("v*.json")))

        return {
            "current_version": metadata.get("current_version"),
            "last_updated": metadata.get("last_updated"),
            "next_check": metadata.get("next_check"),
            "total_supplements": metadata.get("total_supplements", 0),
            "update_frequency_days": metadata.get("update_frequency_days", 30),
            "version_count": version_count
        }


# ==================== CLI 入口 ====================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="知识库更新管理器")
    parser.add_argument("--check", action="store_true", help="检查是否有更新")
    parser.add_argument("--update", action="store_true", help="执行更新")
    parser.add_argument("--force", action="store_true", help="强制更新（忽略时间检查）")
    parser.add_argument("--history", action="store_true", help="查看更新历史")
    parser.add_argument("--status", action="store_true", help="查看当前状态")

    args = parser.parse_args()

    kb = KnowledgeBaseManager()

    if args.check:
        result = kb.check_for_updates()
        print(f"\n需要更新：{result.get('needs_update', False)}")

    elif args.update:
        success, message = kb.update(force=args.force)
        print(f"\n结果：{message}")

    elif args.history:
        history = kb.get_history(limit=10)
        print("=" * 60)
        print("更新历史")
        print("=" * 60)
        for entry in history:
            print(f"\n[{entry['version']}] {entry['timestamp'][:10]}")
            print(f"  操作：{entry['action']}")
            print(f"  补剂：{entry['supplement_name']}")
            if entry.get('diff_summary'):
                print(f"  变更：{entry['diff_summary']}")

    elif args.status:
        status = kb.get_status()
        print("=" * 60)
        print("知识库状态")
        print("=" * 60)
        print(f"当前版本：{status['current_version'] or '无'}")
        print(f"最后更新：{status['last_updated'] or '从未'}")
        print(f"下次检查：{status['next_check'] or '未设置'}")
        print(f"补剂数量：{status['total_supplements']}")
        print(f"更新频率：每 {status['update_frequency_days']} 天")
        print(f"版本数量：{status['version_count']}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
