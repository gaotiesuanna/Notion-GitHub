#!/usr/bin/env python3
"""
同步 data/projects.json 与 data/projects.xlsx。

默认策略:
- 两者都存在时,按最近修改时间选择“源文件”,将其内容写入另一侧。
- 仅存在一侧时,从存在的一侧同步到另一侧。
- 可通过 --direction 强制同步方向。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from project_store import load_projects_config_file, save_projects_config_file


def _normalize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    categories = config.get("categories")
    if isinstance(categories, list):
        return {"categories": categories}

    projects = config.get("projects")
    if isinstance(projects, list):
        return {
            "categories": [
                {
                    "id": "uncategorized",
                    "name": "uncategorized",
                    "icon": "📁",
                    "projects": projects,
                }
            ]
        }
    return {"categories": []}


def _load_json_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return _normalize_config(raw)


def _save_json_config(config: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _load_xlsx_config(path: Path, project_root: Path) -> Dict[str, Any]:
    config, _, _ = load_projects_config_file(str(path), project_root)
    return _normalize_config(config)


def _choose_source(direction: str, json_path: Path, xlsx_path: Path) -> str:
    if direction == "json-to-xlsx":
        if not json_path.exists():
            raise FileNotFoundError(f"JSON 文件不存在: {json_path}")
        return "json"
    if direction == "xlsx-to-json":
        if not xlsx_path.exists():
            raise FileNotFoundError(f"XLSX 文件不存在: {xlsx_path}")
        return "xlsx"

    json_exists = json_path.exists()
    xlsx_exists = xlsx_path.exists()
    if not json_exists and not xlsx_exists:
        raise FileNotFoundError(f"JSON/XLSX 都不存在: {json_path} / {xlsx_path}")
    if json_exists and not xlsx_exists:
        return "json"
    if xlsx_exists and not json_exists:
        return "xlsx"

    json_mtime = json_path.stat().st_mtime
    xlsx_mtime = xlsx_path.stat().st_mtime
    return "json" if json_mtime >= xlsx_mtime else "xlsx"


def sync_files(json_file: str, xlsx_file: str, direction: str, dry_run: bool) -> None:
    project_root = Path(__file__).resolve().parent.parent
    json_path = (project_root / json_file).resolve()
    xlsx_path = (project_root / xlsx_file).resolve()

    source = _choose_source(direction, json_path, xlsx_path)
    if source == "json":
        config = _load_json_config(json_path)
        if dry_run:
            print(f"[DRY-RUN] 将从 JSON 同步到 XLSX: {json_path} -> {xlsx_path}")
            return
        save_projects_config_file(config, str(xlsx_path), project_root)
        print(f"✓ 已同步: {json_path} -> {xlsx_path}")
        return

    config = _load_xlsx_config(xlsx_path, project_root)
    if dry_run:
        print(f"[DRY-RUN] 将从 XLSX 同步到 JSON: {xlsx_path} -> {json_path}")
        return
    _save_json_config(config, json_path)
    print(f"✓ 已同步: {xlsx_path} -> {json_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="双向同步 projects.json 与 projects.xlsx")
    parser.add_argument("--json", default="data/projects.json", help="JSON 文件路径(相对项目根目录)")
    parser.add_argument("--xlsx", default="data/projects.xlsx", help="XLSX 文件路径(相对项目根目录)")
    parser.add_argument(
        "--direction",
        choices=["auto", "json-to-xlsx", "xlsx-to-json"],
        default="auto",
        help="同步方向,默认 auto(按最近修改时间选择源文件)",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅打印将执行的同步动作")
    args = parser.parse_args()

    try:
        sync_files(
            json_file=args.json,
            xlsx_file=args.xlsx,
            direction=args.direction,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"❌ 同步失败: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
