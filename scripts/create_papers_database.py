#!/usr/bin/env python3
"""
创建 Notion 论文数据库（Papers）。

用法示例：
  python scripts/create_papers_database.py
  python scripts/create_papers_database.py --name "Papers" --parent-page-id "<PAGE_ID>"

环境变量：
  NOTION_TOKEN             必填，Notion Integration Token
  NOTION_PARENT_PAGE_ID    必填，数据库挂载到哪个页面下
  PAPERS_DATABASE_NAME     可选，数据库名称，默认 "Papers"
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Dict, Any

import requests

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


NOTION_VERSION = "2022-06-28"
DEFAULT_DB_NAME = "Papers"


def load_local_env_file(env_path: Path) -> None:
    """无 python-dotenv 时的简易 .env 加载器。"""
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="创建 Notion 论文数据库")
    parser.add_argument("--name", help="数据库名称（默认读取 PAPERS_DATABASE_NAME 或 Papers）")
    parser.add_argument("--parent-page-id", help="父页面 ID（默认读取 NOTION_PARENT_PAGE_ID）")
    return parser.parse_args()


def normalize_notion_id(raw: str) -> str:
    """支持粘贴 URL 或带短横线/不带短横线的 ID。"""
    value = (raw or "").strip()
    if not value:
        return value
    if "/" in value:
        value = value.rstrip("/").split("/")[-1]
    if "?" in value:
        value = value.split("?", 1)[0]
    value = value.replace("-", "")
    if len(value) == 32:
        return f"{value[0:8]}-{value[8:12]}-{value[12:16]}-{value[16:20]}-{value[20:32]}"
    return raw.strip()


def get_required(name: str, cli_value: str | None = None) -> str:
    value = (cli_value or os.getenv(name, "")).strip()
    if not value:
        raise ValueError(f"缺少必填配置: {name}")
    return value


def build_database_payload(parent_page_id: str, db_name: str) -> Dict[str, Any]:
    return {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "icon": {"type": "emoji", "emoji": "📚"},
        "title": [{"type": "text", "text": {"content": db_name}}],
        "properties": {
            "标题": {"title": {}},
            "论文链接": {"url": {}},
            "PDF链接": {"url": {}},
            "arXiv ID": {"rich_text": {}},
            "作者": {"rich_text": {}},
            "年份": {"number": {"format": "number"}},
            "会议/期刊": {"select": {}},
            "关键词": {"multi_select": {}},
            "状态": {
                "select": {
                    "options": [
                        {"name": "to_read", "color": "default"},
                        {"name": "reading", "color": "blue"},
                        {"name": "done", "color": "green"},
                    ]
                }
            },
            "评分": {"number": {"format": "number"}},
            "笔记": {"rich_text": {}},
            "分类": {"select": {}},
            "DOI": {"rich_text": {}},
            "Code链接": {"url": {}},
        },
    }


def create_database(notion_token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    response = requests.post(
        "https://api.notion.com/v1/databases",
        headers=headers,
        json=payload,
        timeout=20,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"创建数据库失败: HTTP {response.status_code}\n{response.text}"
        )
    return response.json()


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        if load_dotenv:
            load_dotenv(dotenv_path=env_file)
        else:
            load_local_env_file(env_file)

    args = parse_args()

    notion_token = get_required("NOTION_TOKEN")
    parent_page_id = normalize_notion_id(get_required("NOTION_PARENT_PAGE_ID", args.parent_page_id))
    db_name = (args.name or os.getenv("PAPERS_DATABASE_NAME", DEFAULT_DB_NAME)).strip() or DEFAULT_DB_NAME

    payload = build_database_payload(parent_page_id=parent_page_id, db_name=db_name)
    result = create_database(notion_token=notion_token, payload=payload)

    database_id = result.get("id", "")
    database_url = result.get("url", "")
    print("✅ 论文数据库创建成功")
    print(f"- 名称: {db_name}")
    print(f"- Database ID: {database_id}")
    print(f"- URL: {database_url}")
    print("\n下一步：把 .env 中 NOTION_PAPERS_DATABASE_ID 更新为上面的 Database ID。")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ {e}")
        raise SystemExit(1)
