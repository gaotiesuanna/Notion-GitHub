#!/usr/bin/env python3
"""
按 Notion 页面中的“分类”字段,回写并对齐 projects.xlsx 的 categories 结构。
"""

import argparse
import copy
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.exceptions import ProxyError
from project_store import (
    DEFAULT_CONFIG_FILENAME,
    load_projects_config_file,
    save_projects_config_file,
)

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def load_local_env_file(env_path: Path):
    """无 python-dotenv 时的简易 .env 加载器"""
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


class NotionCategoryReconciler:
    def __init__(self, notion_token: str):
        self.notion_headers = {
            "Authorization": f"Bearer {notion_token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }
        self.notion_session = requests.Session()
        self.notion_direct_session = requests.Session()
        self.notion_direct_session.trust_env = False

    def notion_request(self, method: str, url: str, **kwargs):
        """Notion 请求: 代理失败时自动回退直连"""
        try:
            return self.notion_session.request(
                method, url, headers=self.notion_headers, timeout=10, **kwargs
            )
        except ProxyError:
            print("  ⚠ 代理连接 Notion 失败,正在尝试直连...")
            return self.notion_direct_session.request(
                method, url, headers=self.notion_headers, timeout=10, **kwargs
            )

    def get_page_category(self, page_id: str) -> Optional[str]:
        """读取单个 Notion 页面“分类”字段值"""
        url = f"https://api.notion.com/v1/pages/{page_id}"
        response = self.notion_request("GET", url)
        if response.status_code != 200:
            print(f"  ⚠ 读取 Notion 页面失败: {page_id} ({response.status_code})")
            return None

        properties = response.json().get("properties", {})
        category_prop = properties.get("分类")
        if not category_prop:
            return None

        prop_type = category_prop.get("type")
        if prop_type == "select":
            select_data = category_prop.get("select")
            return (select_data or {}).get("name")

        if prop_type == "multi_select":
            options = category_prop.get("multi_select") or []
            if not options:
                return None
            return options[0].get("name")

        if prop_type == "rich_text":
            texts = category_prop.get("rich_text") or []
            raw = "".join((item.get("plain_text") or "") for item in texts).strip()
            return raw or None

        print(f"  ⚠ 页面 {page_id} 的“分类”字段类型为 {prop_type},已跳过")
        return None


def slugify(text: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", text.strip().lower())
    normalized = normalized.strip("-")
    return normalized or "category"


def ensure_category(config: Dict[str, Any], category_name: str) -> Dict[str, Any]:
    categories = config.setdefault("categories", [])
    for category in categories:
        if category.get("name") == category_name:
            category.setdefault("projects", [])
            return category

    existing_ids = {str(c.get("id", "")).strip() for c in categories}
    base_id = slugify(category_name)
    candidate = base_id
    i = 2
    while candidate in existing_ids:
        candidate = f"{base_id}-{i}"
        i += 1

    category = {
        "id": candidate,
        "name": category_name,
        "icon": "📁",
        "projects": [],
    }
    categories.append(category)
    return category


def build_project_locations(
    config: Dict[str, Any],
) -> List[Tuple[Dict[str, Any], Dict[str, Any], int]]:
    """返回 (category, project, index)"""
    result: List[Tuple[Dict[str, Any], Dict[str, Any], int]] = []
    for category in config.get("categories", []):
        projects = category.get("projects", [])
        if not isinstance(projects, list):
            continue
        for idx, project in enumerate(projects):
            if isinstance(project, dict):
                result.append((category, project, idx))
    return result


def reconcile_projects(
    config: Dict[str, Any], reconciler: NotionCategoryReconciler
) -> Tuple[int, int, int]:
    moved_count = 0
    created_category_count = 0
    skipped_count = 0

    # 用快照遍历,避免遍历期间移动导致索引混乱
    snapshot = build_project_locations(config)

    for source_category, project, _ in snapshot:
        project_id = project.get("id", "unknown")
        page_id = (project.get("notion_page_id") or "").strip()
        if not page_id:
            skipped_count += 1
            continue

        notion_category = reconciler.get_page_category(page_id)
        if not notion_category:
            skipped_count += 1
            continue

        source_name = source_category.get("name")
        if source_name == notion_category:
            continue

        categories_before = len(config.get("categories", []))
        target_category = ensure_category(config, notion_category)
        if len(config.get("categories", [])) > categories_before:
            created_category_count += 1
            print(f"  + 新增分类: {notion_category}")

        source_projects = source_category.get("projects", [])
        source_index = next(
            (i for i, p in enumerate(source_projects) if p.get("id") == project_id), -1
        )
        if source_index < 0:
            skipped_count += 1
            continue

        target_projects = target_category.setdefault("projects", [])
        if any(p.get("id") == project_id for p in target_projects):
            source_projects.pop(source_index)
            print(
                f"  ↷ 项目 {project_id} 已在分类“{notion_category}”中,已从“{source_name}”移除重复项"
            )
            moved_count += 1
            continue

        moving_project = source_projects.pop(source_index)
        target_projects.append(copy.deepcopy(moving_project))
        print(f"  → 项目 {project_id}: {source_name} -> {notion_category}")
        moved_count += 1

    return moved_count, created_category_count, skipped_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="按 Notion 页面“分类”字段回写 projects.xlsx"
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_FILENAME,
        help="配置文件路径 (默认: 脚本同目录下的 projects.xlsx)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="实际写入文件 (默认仅 dry-run)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    script_dir = Path(__file__).resolve().parent

    env_file = script_dir / ".env"
    if env_file.exists():
        if load_dotenv:
            load_dotenv(dotenv_path=env_file)
        else:
            load_local_env_file(env_file)

    notion_token = os.environ.get("NOTION_TOKEN", "").strip()
    if not notion_token:
        print("❌ 未设置 NOTION_TOKEN")
        return

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = script_dir / config_path
    config, resolved_path, migrated = load_projects_config_file(str(config_path), script_dir)
    if migrated:
        print("✓ 已从旧版 JSON 自动迁移为 Excel 配置")

    if not isinstance(config.get("categories"), list):
        print("❌ 当前仅支持 categories 结构的项目配置")
        return

    print(f"开始对齐分类: {resolved_path}")
    print(f"模式: {'apply' if args.apply else 'dry-run'}")
    reconciler = NotionCategoryReconciler(notion_token=notion_token)
    moved_count, created_count, skipped_count = reconcile_projects(config, reconciler)

    print("\n结果统计:")
    print(f"  移动项目: {moved_count}")
    print(f"  新增分类: {created_count}")
    print(f"  跳过项目: {skipped_count}")

    if not args.apply:
        print("\n当前为 dry-run,未写入文件。使用 --apply 执行落盘。")
        return

    saved_path = save_projects_config_file(config, str(resolved_path), script_dir)
    print(f"\n✓ 已写入: {saved_path}")


if __name__ == "__main__":
    main()
