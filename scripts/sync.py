#!/usr/bin/env python3
"""
GitHub 项目信息自动同步到 Notion
支持从 Excel 配置文件读取项目列表并自动同步
"""

import os
import requests
from requests.exceptions import ProxyError
from typing import Any, Dict, List, Optional, Tuple
import time
from pathlib import Path
from reconcile_categories_from_notion import (
    NotionCategoryReconciler,
    reconcile_projects,
)
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

    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

class GitHubNotionSync:
    def __init__(self, notion_token: str, database_id: str, github_token: Optional[str] = None):
        """
        初始化同步器
        
        Args:
            notion_token: Notion Integration Token
            database_id: Notion 数据库 ID
            github_token: GitHub Personal Access Token (可选,用于提高 API 限制)
        """
        self.notion_token = notion_token
        self.database_id = database_id
        self.github_token = github_token
        
        self.notion_headers = {
            "Authorization": f"Bearer {notion_token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        # 默认会读取系统代理; 当代理故障时自动切换到直连会话
        self.notion_session = requests.Session()
        self.notion_direct_session = requests.Session()
        self.notion_direct_session.trust_env = False
        
        self.github_headers = {}
        if github_token:
            self.github_headers["Authorization"] = f"token {github_token}"
        self._database_properties: Optional[Dict[str, Any]] = None
        self._warned_missing_category_property = False
        self._github_url_page_index: Optional[Dict[str, List[str]]] = None

    @staticmethod
    def parse_category_name_from_properties(properties: Dict[str, Any]) -> Optional[str]:
        """从 Notion 页面 properties 中提取“分类”字段文本值"""
        category_prop = (properties or {}).get("分类")
        if not category_prop:
            return None

        prop_type = category_prop.get("type")
        if prop_type == "select":
            select_data = category_prop.get("select") or {}
            return (select_data.get("name") or "").strip() or None
        if prop_type == "multi_select":
            options = category_prop.get("multi_select") or []
            if not options:
                return None
            return (options[0].get("name") or "").strip() or None
        if prop_type == "rich_text":
            texts = category_prop.get("rich_text") or []
            raw = "".join((item.get("plain_text") or "") for item in texts).strip()
            return raw or None
        return None

    @staticmethod
    def normalize_github_url(raw_url: str) -> str:
        """统一 GitHub 链接格式,用于稳定匹配"""
        return (raw_url or "").strip().rstrip("/").lower()

    @staticmethod
    def slugify(text: str) -> str:
        normalized = "".join(
            ch if (ch.isalnum() or ch in {"-", "_"} or "\u4e00" <= ch <= "\u9fff") else "-"
            for ch in (text or "").strip().lower()
        )
        normalized = "-".join(part for part in normalized.split("-") if part)
        return normalized or "category"

    @staticmethod
    def normalize_notion_page_id(raw_page_id: str) -> str:
        return (raw_page_id or "").strip().replace("-", "").lower()

    @staticmethod
    def parse_repo_name_from_github_url(github_url: str) -> str:
        parts = [p for p in (github_url or "").strip().rstrip("/").split("/") if p]
        if len(parts) >= 2:
            return parts[-1]
        return ""

    def notion_request(self, method: str, url: str, **kwargs):
        """Notion 请求: 代理失败时自动回退直连"""
        try:
            return self.notion_session.request(method, url, headers=self.notion_headers, timeout=10, **kwargs)
        except ProxyError:
            print("  ⚠ 代理连接 Notion 失败,正在尝试直连...")
            return self.notion_direct_session.request(method, url, headers=self.notion_headers, timeout=10, **kwargs)

    def get_database_properties(self) -> Dict[str, Any]:
        """读取并缓存 Notion 数据库属性定义"""
        if self._database_properties is not None:
            return self._database_properties

        try:
            url = f"https://api.notion.com/v1/databases/{self.database_id}"
            response = self.notion_request("GET", url)
            if response.status_code == 200:
                self._database_properties = response.json().get("properties", {})
            else:
                self._database_properties = {}
        except Exception:
            self._database_properties = {}

        return self._database_properties

    def get_property_type(self, property_name: str) -> str:
        """获取数据库属性类型,未知时返回空字符串"""
        properties = self.get_database_properties()
        property_def = properties.get(property_name, {})
        return property_def.get("type", "")

    def preload_notion_github_page_index(self) -> Dict[str, List[str]]:
        """
        预加载 Notion 数据库中全部 GitHub 链接 -> page_id 索引。
        用于 create_only / update_only 快速判定,避免逐条远程回查。
        """
        if self._github_url_page_index is not None:
            return self._github_url_page_index

        index: Dict[str, List[str]] = {}
        github_link_type = self.get_property_type("GitHub 链接")
        if github_link_type != "url":
            self._github_url_page_index = index
            return index

        print("预检 Notion 现有页面索引...")
        query_url = f"https://api.notion.com/v1/databases/{self.database_id}/query"
        start_cursor: Optional[str] = None
        fetched_pages = 0

        try:
            while True:
                payload: Dict[str, Any] = {"page_size": 100}
                if start_cursor:
                    payload["start_cursor"] = start_cursor

                response = self.notion_request("POST", query_url, json=payload)
                if response.status_code != 200:
                    print(f"  ⚠ 预检索引失败 ({response.status_code}),将回退逐条回查")
                    break

                data = response.json()
                results = data.get("results", [])
                fetched_pages += len(results)
                for item in results:
                    page_id = item.get("id")
                    properties = item.get("properties", {})
                    github_prop = properties.get("GitHub 链接", {})
                    github_url = self.normalize_github_url(github_prop.get("url", ""))
                    if not page_id or not github_url:
                        continue
                    index.setdefault(github_url, []).append(page_id)

                if not data.get("has_more"):
                    break
                start_cursor = data.get("next_cursor")
                if not start_cursor:
                    break
        except Exception as e:
            print(f"  ⚠ 预检索引出错: {str(e)},将回退逐条回查")

        self._github_url_page_index = index
        print(
            f"  ✓ 索引完成: 扫描 {fetched_pages} 页记录,可匹配 GitHub 链接 {len(index)} 条"
        )
        return index

    def fetch_notion_github_records(self) -> Dict[str, List[Dict[str, str]]]:
        """
        扫描 Notion 数据库,返回:
        github_url(normalized) -> [{page_id, category_name}]
        """
        records: Dict[str, List[Dict[str, str]]] = {}
        github_link_type = self.get_property_type("GitHub 链接")
        if github_link_type != "url":
            print("  ⚠ Notion 的“GitHub 链接”字段不是 url 类型,无法执行本地回写校正")
            return records

        print("从 Notion 拉取项目索引(含分类)...")
        query_url = f"https://api.notion.com/v1/databases/{self.database_id}/query"
        start_cursor: Optional[str] = None
        fetched_pages = 0

        while True:
            payload: Dict[str, Any] = {"page_size": 100}
            if start_cursor:
                payload["start_cursor"] = start_cursor

            response = self.notion_request("POST", query_url, json=payload)
            if response.status_code != 200:
                print(f"  ⚠ 拉取 Notion 索引失败 ({response.status_code})")
                break

            data = response.json()
            results = data.get("results", [])
            fetched_pages += len(results)
            for item in results:
                page_id = (item or {}).get("id", "")
                properties = (item or {}).get("properties", {})
                github_prop = properties.get("GitHub 链接", {})
                github_url = self.normalize_github_url(github_prop.get("url", ""))
                if not page_id or not github_url:
                    continue
                category_name = self.parse_category_name_from_properties(properties) or ""
                records.setdefault(github_url, []).append(
                    {
                        "page_id": page_id,
                        "category_name": category_name,
                    }
                )

            if not data.get("has_more"):
                break
            start_cursor = data.get("next_cursor")
            if not start_cursor:
                break

        print(f"  ✓ 拉取完成: 扫描 {fetched_pages} 页记录,命中 GitHub 链接 {len(records)} 条")
        return records

    def fetch_notion_projects(self) -> List[Dict[str, Any]]:
        """扫描 Notion 数据库并提取最小项目信息,用于回写本地配置"""
        records: List[Dict[str, Any]] = []
        github_link_type = self.get_property_type("GitHub 链接")
        if github_link_type != "url":
            print("  ⚠ Notion 的“GitHub 链接”字段不是 url 类型,无法拉取项目")
            return records

        print("从 Notion 拉取项目(用于本地合并)...")
        query_url = f"https://api.notion.com/v1/databases/{self.database_id}/query"
        start_cursor: Optional[str] = None
        fetched_pages = 0

        while True:
            payload: Dict[str, Any] = {"page_size": 100}
            if start_cursor:
                payload["start_cursor"] = start_cursor

            response = self.notion_request("POST", query_url, json=payload)
            if response.status_code != 200:
                print(f"  ⚠ 拉取 Notion 项目失败 ({response.status_code})")
                break

            data = response.json()
            results = data.get("results", [])
            fetched_pages += len(results)
            for item in results:
                if (item or {}).get("object") != "page":
                    continue

                page_id = (item or {}).get("id", "")
                properties = (item or {}).get("properties", {})
                github_prop = properties.get("GitHub 链接", {})
                github_url = self.normalize_github_url(github_prop.get("url", ""))
                if not page_id or not github_url:
                    continue

                title_items = ((properties.get("项目名称") or {}).get("title") or [])
                project_name = "".join((node.get("plain_text") or "") for node in title_items).strip()
                desc_items = ((properties.get("描述") or {}).get("rich_text") or [])
                description = "".join((node.get("plain_text") or "") for node in desc_items).strip()
                topic_items = ((properties.get("技术标签") or {}).get("multi_select") or [])
                topics = [str((node or {}).get("name") or "").strip() for node in topic_items]
                topics = [x for x in topics if x]
                category_name = self.parse_category_name_from_properties(properties) or ""
                repo_name = self.parse_repo_name_from_github_url(github_url)
                project_id = repo_name.lower() if repo_name else self.slugify(project_name or github_url)

                records.append(
                    {
                        "id": project_id,
                        "name": project_name or repo_name,
                        "description": description,
                        "github": github_url,
                        "topics": topics,
                        "notion_page_id": page_id,
                        "category_name": category_name,
                    }
                )

            if not data.get("has_more"):
                break
            start_cursor = data.get("next_cursor")
            if not start_cursor:
                break

        print(f"  ✓ 拉取完成: 扫描 {fetched_pages} 页记录,可合并项目 {len(records)} 条")
        return records

    def ensure_category_in_config(self, config: Dict[str, Any], category_name: str) -> Dict[str, Any]:
        """确保配置中存在指定分类(按 name 匹配)"""
        categories = config.setdefault("categories", [])
        for category in categories:
            if category.get("name") == category_name:
                category.setdefault("projects", [])
                return category

        existing_ids = {str(c.get("id", "")).strip() for c in categories}
        base_id = self.slugify(category_name)
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

    def reconcile_local_ids_and_categories_from_notion(self, config: Dict[str, Any]) -> Dict[str, int]:
        """
        从 Notion 拉取并回写本地:
        - notion_page_id
        - 分类
        规则:
        - 若本地 notion_page_id 与 Notion(按 GitHub 链接匹配到的 page_id)不一致,仅清空 notion_page_id
        - 条目始终保留,不删除
        """
        stats = {
            "filled_page_id": 0,
            "cleared_page_id": 0,
            "moved_category": 0,
            "created_category": 0,
            "no_match": 0,
            "duplicate_in_notion": 0,
        }

        records = self.fetch_notion_github_records()
        categories = config.get("categories", [])
        if not isinstance(categories, list):
            return stats

        # 快照遍历,避免移动项目时影响迭代
        snapshot: List[Dict[str, Any]] = []
        for category in categories:
            for project in category.get("projects", []):
                if isinstance(project, dict):
                    snapshot.append(project)

        for project in snapshot:
            github_url = self.normalize_github_url(project.get("github", ""))
            if not github_url:
                continue

            matched = records.get(github_url, [])
            if not matched:
                if (project.get("notion_page_id") or "").strip():
                    project["notion_page_id"] = ""
                    stats["cleared_page_id"] += 1
                stats["no_match"] += 1
                continue

            if len(matched) > 1:
                stats["duplicate_in_notion"] += 1
            remote_page_id = (matched[0].get("page_id") or "").strip()
            remote_category_name = (matched[0].get("category_name") or "").strip()

            local_page_id = (project.get("notion_page_id") or "").strip()
            if local_page_id and local_page_id != remote_page_id:
                project["notion_page_id"] = ""
                stats["cleared_page_id"] += 1
            elif not local_page_id and remote_page_id:
                project["notion_page_id"] = remote_page_id
                stats["filled_page_id"] += 1

            if remote_category_name:
                source_category = None
                source_index = -1
                for category in categories:
                    projects = category.get("projects", [])
                    for idx, item in enumerate(projects):
                        if item is project:
                            source_category = category
                            source_index = idx
                            break
                    if source_category:
                        break

                if source_category and source_category.get("name") != remote_category_name:
                    before_count = len(categories)
                    target_category = self.ensure_category_in_config(config, remote_category_name)
                    if len(categories) > before_count:
                        stats["created_category"] += 1

                    target_projects = target_category.setdefault("projects", [])
                    if not any(item is project for item in target_projects):
                        moving_project = source_category.get("projects", []).pop(source_index)
                        target_projects.append(moving_project)
                        stats["moved_category"] += 1

        return stats

    def build_stars_property(self, stars: int) -> Dict[str, Any]:
        """根据数据库字段类型构建 Stars 属性值"""
        if stars >= 1000:
            stars_k = f"{stars / 1000:.1f}".rstrip("0").rstrip(".")
            stars_text = f"⭐ {stars_k}k"
        else:
            stars_text = f"⭐ {stars}"
        stars_type = self.get_property_type("Stars")

        if stars_type == "rich_text":
            return {
                "Stars": {
                    "rich_text": [
                        {
                            "text": {
                                "content": stars_text
                            }
                        }
                    ]
                }
            }

        # 默认按 number 写入,兼容现有数据库
        return {
            "Stars": {
                "number": stars
            }
        }

    def build_stars_init_property(self, stars: int) -> Dict[str, Any]:
        """构建 Stars_init 属性值(纯数值)"""
        stars_init_type = self.get_property_type("Stars_init")
        if stars_init_type == "number":
            return {
                "Stars_init": {
                    "number": stars
                }
            }
        return {}

    def build_category_property(self, category_name: Optional[str]) -> Dict[str, Any]:
        """根据数据库字段类型构建 分类 属性值"""
        if not category_name:
            return {}

        category_type = self.get_property_type("分类")
        if not category_type:
            if not self._warned_missing_category_property:
                print("  ⚠ 未在 Notion 数据库中找到“分类”字段,将跳过该字段写入")
                self._warned_missing_category_property = True
            return {}

        if category_type == "select":
            return {
                "分类": {
                    "select": {
                        "name": category_name
                    }
                }
            }

        if category_type == "multi_select":
            return {
                "分类": {
                    "multi_select": [
                        {"name": category_name}
                    ]
                }
            }

        if category_type == "rich_text":
            return {
                "分类": {
                    "rich_text": [
                        {
                            "text": {
                                "content": category_name
                            }
                        }
                    ]
                }
            }

        print(f"  ⚠ “分类”字段类型为 {category_type},暂不支持自动写入")
        return {}

    def extract_projects_with_category(self, config: Dict[str, Any]) -> List[Tuple[Dict[str, Any], Optional[str]]]:
        """兼容旧版 projects 与新版 categories 结构"""
        categories = config.get("categories", [])
        if isinstance(categories, list) and categories:
            result: List[Tuple[Dict[str, Any], Optional[str]]] = []
            for category in categories:
                category_name = category.get("name", "")
                for project in category.get("projects", []):
                    result.append((project, category_name))
            return result

        return [(project, None) for project in config.get("projects", [])]

    def merge_notion_projects_into_config(self, config: Dict[str, Any]) -> Dict[str, int]:
        """
        将 Notion 中项目合并到本地 config。
        - 支持从 Notion 新增项目到本地
        - 对已存在项目补齐缺失字段
        - 可按 Notion 分类移动到对应分类
        """
        stats = {
            "total_notion": 0,
            "inserted": 0,
            "merged": 0,
            "filled_fields": 0,
            "moved_category": 0,
            "created_category": 0,
        }

        categories = config.setdefault("categories", [])
        if not isinstance(categories, list):
            config["categories"] = []
            categories = config["categories"]

        for category in categories:
            category.setdefault("projects", [])

        notion_projects = self.fetch_notion_projects()
        stats["total_notion"] = len(notion_projects)
        if not notion_projects:
            return stats

        def locate_project(project_ref: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], int]:
            for c in categories:
                projects = c.get("projects", [])
                for idx, p in enumerate(projects):
                    if p is project_ref:
                        return c, idx
            return None, -1

        def find_existing_project(notion_project: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            target_page_id = self.normalize_notion_page_id(notion_project.get("notion_page_id", ""))
            target_github = self.normalize_github_url(notion_project.get("github", ""))
            for c in categories:
                for p in c.get("projects", []):
                    page_id = self.normalize_notion_page_id(p.get("notion_page_id", ""))
                    github = self.normalize_github_url(p.get("github", ""))
                    if target_page_id and page_id and target_page_id == page_id:
                        return p
                    if target_github and github and target_github == github:
                        return p
            return None

        def fill_missing(target: Dict[str, Any], source: Dict[str, Any]) -> int:
            changed = 0
            for field in ["id", "name", "description", "github", "notion_page_id"]:
                current = str(target.get(field, "") or "").strip()
                incoming = str(source.get(field, "") or "").strip()
                if (not current) and incoming:
                    target[field] = incoming
                    changed += 1
            current_topics = target.get("topics") or []
            incoming_topics = source.get("topics") or []
            if (not current_topics) and incoming_topics:
                target["topics"] = incoming_topics
                changed += 1
            return changed

        for notion_project in notion_projects:
            existing = find_existing_project(notion_project)
            category_name = (notion_project.get("category_name") or "").strip() or "未分类"
            before_count = len(categories)
            target_category = self.ensure_category_in_config(config, category_name)
            if len(categories) > before_count:
                stats["created_category"] += 1

            if existing is None:
                new_project = {
                    "id": str(notion_project.get("id") or "").strip(),
                    "name": str(notion_project.get("name") or "").strip(),
                    "description": str(notion_project.get("description") or "").strip(),
                    "github": str(notion_project.get("github") or "").strip(),
                    "topics": list(notion_project.get("topics") or []),
                    "notion_page_id": str(notion_project.get("notion_page_id") or "").strip(),
                }
                target_category.setdefault("projects", []).append(new_project)
                stats["inserted"] += 1
                continue

            stats["merged"] += 1
            stats["filled_fields"] += fill_missing(existing, notion_project)
            src_category, src_index = locate_project(existing)
            if src_category is not None and src_category is not target_category and src_index >= 0:
                moving = src_category.get("projects", []).pop(src_index)
                target_category.setdefault("projects", []).append(moving)
                stats["moved_category"] += 1

        return stats

    def hydrate_local_project_from_github(self, project: Dict[str, Any], github_info: Dict[str, Any]) -> int:
        """将 GitHub API 信息回填到本地项目(仅补空字段)"""
        changed = 0
        fallback_id = str(github_info.get("name") or "").strip().lower()
        if not (project.get("id") or "").strip() and fallback_id:
            project["id"] = fallback_id
            changed += 1

        if not (project.get("name") or "").strip():
            name = str(github_info.get("name") or "").strip()
            if name:
                project["name"] = name
                changed += 1

        if not (project.get("description") or "").strip():
            desc = str(github_info.get("description") or "").strip()
            if desc and desc != "暂无描述":
                project["description"] = desc
                changed += 1

        if not (project.get("topics") or []):
            topics = github_info.get("topics") or []
            if topics:
                project["topics"] = topics
                changed += 1
        return changed
    
    def load_projects_config(self, config_file: str) -> Dict:
        """加载项目配置文件"""
        try:
            project_root = Path(__file__).resolve().parent.parent
            config, resolved_path, migrated = load_projects_config_file(config_file, project_root)
            project_count = len(self.extract_projects_with_category(config))
            print(f"✓ 成功加载配置文件: {resolved_path}")
            if migrated:
                print("  ✓ 已从旧版 JSON 自动迁移为 Excel 配置")
            print(f"  共 {project_count} 个项目\n")
            return config
        except FileNotFoundError:
            print(f"⚠ 配置文件不存在,创建新文件: {config_file}\n")
            return {"categories": []}
        except Exception as e:
            print(f"✗ 加载配置文件失败: {str(e)}\n")
            return {"categories": []}
    
    def save_projects_config(self, config: Dict, config_file: str):
        """保存项目配置文件"""
        try:
            project_root = Path(__file__).resolve().parent.parent
            saved_path = save_projects_config_file(config, config_file, project_root)
            print(f"\n✓ 配置文件已更新: {saved_path}")
        except Exception as e:
            print(f"\n✗ 保存配置文件失败: {str(e)}")
    
    def get_github_repo_info(self, repo_url: str) -> Optional[Dict]:
        """获取 GitHub 仓库的最新信息"""
        try:
            # 从 URL 提取 owner 和 repo
            parts = repo_url.rstrip('/').split('/')
            if len(parts) < 2:
                print(f"  ✗ 无效的 GitHub URL: {repo_url}")
                return None
            
            owner, repo = parts[-2], parts[-1]
            
            # 调用 GitHub API
            api_url = f"https://api.github.com/repos/{owner}/{repo}"
            response = requests.get(api_url, headers=self.github_headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # 提取关键信息
                repo_info = {
                    'name': data['name'],
                    'full_name': data['full_name'],
                    'description': data['description'] or '暂无描述',
                    'url': data['html_url'],
                    'stars': data['stargazers_count'],
                    'forks': data['forks_count'],
                    'watchers': data['watchers_count'],
                    'open_issues': data['open_issues_count'],
                    'language': data['language'] or '未知',
                    'topics': data.get('topics', []),
                    'created_at': data['created_at'],
                    'updated_at': data['updated_at'],
                    'pushed_at': data['pushed_at'],
                    'license': data['license']['name'] if data['license'] else '无',
                    'default_branch': data['default_branch'],
                    'is_archived': data['archived'],
                    'owner': data['owner']['login'],
                }
                
                print(f"  ✓ GitHub API: {repo_info['full_name']} (⭐ {repo_info['stars']:,})")
                return repo_info
            elif response.status_code == 404:
                print(f"  ✗ 仓库不存在: {repo_url}")
                return None
            elif response.status_code == 403:
                print(f"  ✗ API 限制或访问被拒: {repo_url}")
                return None
            else:
                print(f"  ✗ GitHub API 错误 {response.status_code}: {repo_url}")
                return None
                
        except Exception as e:
            print(f"  ✗ 获取仓库信息出错: {str(e)}")
            return None
    
    def find_notion_page_id_by_github_url(self, github_url: str) -> Optional[str]:
        """按 GitHub 链接回查 Notion 页面 ID"""
        github_url = (github_url or "").strip()
        if not github_url:
            return None

        normalized_url = self.normalize_github_url(github_url)
        if self._github_url_page_index is not None:
            page_ids = self._github_url_page_index.get(normalized_url, [])
            if not page_ids:
                return None
            if len(page_ids) > 1:
                print(f"  ⚠ 检测到 {len(page_ids)} 条同 GitHub 链接记录,将使用第一条")
            return page_ids[0]

        github_link_type = self.get_property_type("GitHub 链接")
        if github_link_type != "url":
            # 仅在字段为 url 类型时启用精确回查,避免误匹配
            return None

        try:
            url = f"https://api.notion.com/v1/databases/{self.database_id}/query"
            data = {
                "filter": {
                    "property": "GitHub 链接",
                    "url": {
                        "equals": github_url
                    }
                },
                "page_size": 10
            }
            response = self.notion_request("POST", url, json=data)
            if response.status_code != 200:
                print(f"  ⚠ 回查 Notion 页面失败 ({response.status_code})")
                return None

            results = response.json().get("results", [])
            if not results:
                return None

            if len(results) > 1:
                print(f"  ⚠ 检测到 {len(results)} 条同 GitHub 链接记录,将使用第一条")
            return results[0].get("id")
        except Exception as e:
            print(f"  ⚠ 回查 Notion 页面出错: {str(e)}")
            return None

    def create_notion_page(self, project: Dict, github_info: Dict, category_name: Optional[str] = None) -> Optional[str]:
        """在 Notion 数据库中创建新页面"""
        try:
            url = "https://api.notion.com/v1/pages"
            
            # 构建属性
            properties = {
                "项目名称": {
                    "title": [
                        {
                            "text": {
                                "content": github_info.get('name', project.get('name', '未命名'))
                            }
                        }
                    ]
                },
                "GitHub 链接": {
                    "url": github_info['url']
                },
                "描述": {
                    "rich_text": [
                        {
                            "text": {
                                "content": github_info['description'][:2000]
                            }
                        }
                    ]
                },
                "Forks": {
                    "number": github_info['forks']
                },
                "Watchers": {
                    "number": github_info['watchers']
                },
                "Open Issues": {
                    "number": github_info['open_issues']
                },
                "主要语言": {
                    "select": {
                        "name": github_info['language']
                    }
                },
                "最后更新": {
                    "date": {
                        "start": github_info['updated_at']
                    }
                },
                "最后推送": {
                    "date": {
                        "start": github_info['pushed_at']
                    }
                },
                "作者": {
                    "rich_text": [
                        {
                            "text": {
                                "content": github_info['owner']
                            }
                        }
                    ]
                },
                "许可证": {
                    "select": {
                        "name": github_info['license']
                    }
                },
                "状态": {
                    "select": {
                        "name": "已归档" if github_info['is_archived'] else "活跃"
                    }
                }
            }

            properties.update(self.build_stars_property(github_info['stars']))
            properties.update(self.build_stars_init_property(github_info['stars']))
            properties.update(self.build_category_property(category_name))
            
            # 添加技术标签
            topics = github_info.get('topics', project.get('topics', []))
            if topics:
                properties["技术标签"] = {
                    "multi_select": [
                        {"name": topic} for topic in topics[:10]
                    ]
                }
            
            data = {
                "parent": {"database_id": self.database_id},
                "properties": properties
            }
            
            response = self.notion_request("POST", url, json=data)
            
            if response.status_code == 200:
                page_id = response.json()['id']
                print(f"  ✓ Notion 页面已创建")
                return page_id
            else:
                print(f"  ✗ 创建失败 ({response.status_code}): {response.text[:200]}")
                return None
                
        except Exception as e:
            print(f"  ✗ 创建页面出错: {str(e)}")
            return None
    
    def update_notion_page(self, page_id: str, project: Dict, github_info: Dict, category_name: Optional[str] = None) -> str:
        """更新已存在的 Notion 页面"""
        try:
            url = f"https://api.notion.com/v1/pages/{page_id}"
            
            properties = {
                "项目名称": {
                    "title": [
                        {
                            "text": {
                                "content": github_info.get('name', project.get('name', '未命名'))
                            }
                        }
                    ]
                },
                "GitHub 链接": {
                    "url": github_info['url']
                },
                "描述": {
                    "rich_text": [
                        {
                            "text": {
                                "content": github_info['description'][:2000]
                            }
                        }
                    ]
                },
                "Forks": {
                    "number": github_info['forks']
                },
                "Watchers": {
                    "number": github_info['watchers']
                },
                "Open Issues": {
                    "number": github_info['open_issues']
                },
                "主要语言": {
                    "select": {
                        "name": github_info['language']
                    }
                },
                "最后更新": {
                    "date": {
                        "start": github_info['updated_at']
                    }
                },
                "最后推送": {
                    "date": {
                        "start": github_info['pushed_at']
                    }
                },
                "许可证": {
                    "select": {
                        "name": github_info['license']
                    }
                },
                "状态": {
                    "select": {
                        "name": "已归档" if github_info['is_archived'] else "活跃"
                    }
                }
            }

            properties.update(self.build_stars_property(github_info['stars']))
            properties.update(self.build_stars_init_property(github_info['stars']))
            properties.update(self.build_category_property(category_name))
            
            topics = github_info.get('topics', project.get('topics', []))
            if topics:
                properties["技术标签"] = {
                    "multi_select": [
                        {"name": topic} for topic in topics[:10]
                    ]
                }
            
            data = {"properties": properties}
            
            response = self.notion_request("PATCH", url, json=data)
            
            if response.status_code == 200:
                print(f"  ✓ Notion 页面已更新")
                return "ok"
            if response.status_code == 404:
                print("  ⚠ Notion 页面不存在(可能已删除或 page_id 失效)")
                return "not_found"
            else:
                print(f"  ✗ 更新失败 ({response.status_code}): {response.text[:200]}")
                return "error"
                
        except Exception as e:
            print(f"  ✗ 更新页面出错: {str(e)}")
            return "error"
    
    def sync_project(self, project: Dict, category_name: Optional[str] = None) -> Tuple[Optional[str], str]:
        """同步单个项目"""
        print(f"\n{'='*60}")
        print(f"[{project.get('id', 'unknown')}] {project.get('name', project['github'])}")
        if category_name:
            print(f"分类: {category_name}")
        print('='*60)
        
        # 获取 GitHub 最新信息
        github_info = self.get_github_repo_info(project['github'])
        if not github_info:
            print("  ⚠ 跳过此项目")
            return project.get('notion_page_id'), "skipped"
        self.hydrate_local_project_from_github(project, github_info)
        
        # 优先使用本地记录的 notion_page_id;若失效/缺失则按 GitHub 链接回查
        notion_page_id = project.get('notion_page_id', '').strip()

        if notion_page_id:
            update_status = self.update_notion_page(notion_page_id, project, github_info, category_name)
            if update_status == "ok":
                return notion_page_id, "updated"
            if update_status == "error":
                # 非 404 错误不自动创建,避免网络抖动导致重复页面
                return None, "failed"
            # 仅在确认 not_found 时继续回查/创建

        recovered_page_id = self.find_notion_page_id_by_github_url(github_info.get("url", project.get("github", "")))
        if recovered_page_id:
            print("  ✓ 已通过 GitHub 链接回查到现有 Notion 页面")
            success = self.update_notion_page(recovered_page_id, project, github_info, category_name)
            if success:
                return recovered_page_id, "updated"

        # 回查不到或回查后更新失败,创建新页面
        page_id = self.create_notion_page(project, github_info, category_name)
        if page_id:
            return page_id, "created"
        return None, "missing_remote"
    
    def sync_all_projects(self, config_file: str = DEFAULT_CONFIG_FILENAME, sync_mode: str = 'all'):
        """同步所有项目"""
        print("\n" + "="*60)
        print("GitHub → Notion 同步工具")
        print(f"同步模式: {sync_mode}")
        print("="*60 + "\n")
        
        # 加载配置
        config = self.load_projects_config(config_file)
        projects_with_category = self.extract_projects_with_category(config)
        
        if not projects_with_category:
            print("⚠ 配置文件中没有项目\n")
            return
        
        print(f"开始同步 {len(projects_with_category)} 个项目...\n")

        if sync_mode in {'create_only', 'update_only'}:
            self.preload_notion_github_page_index()

        projects_to_sync = projects_with_category
        updated_count = 0
        created_count = 0
        failed_count = 0
        skipped_count = 0

        if sync_mode == 'create_only':
            pending: List[Tuple[Dict[str, Any], Optional[str]]] = []
            recovered_count = 0
            for project, category_name in projects_with_category:
                had_page_id = bool(project.get('notion_page_id', '').strip())
                if not had_page_id:
                    recovered_page_id = self.find_notion_page_id_by_github_url(project.get('github', ''))
                    if recovered_page_id:
                        project['notion_page_id'] = recovered_page_id
                        had_page_id = True
                        recovered_count += 1
                missing_core = any(
                    [
                        not (project.get('name') or '').strip(),
                        not (project.get('description') or '').strip(),
                        not (project.get('topics') or []),
                    ]
                )
                if had_page_id and not missing_core:
                    skipped_count += 1
                else:
                    pending.append((project, category_name))
            projects_to_sync = pending
            print(f"create_only 预检: 待处理 {len(projects_to_sync)} 个,完整且已存在 {skipped_count} 个")
            if recovered_count > 0:
                print(f"  ✓ 其中按 GitHub 链接补齐 notion_page_id: {recovered_count} 个")

        elif sync_mode == 'update_only':
            pending = []
            recovered_count = 0
            for project, category_name in projects_with_category:
                had_page_id = bool(project.get('notion_page_id', '').strip())
                if not had_page_id:
                    recovered_page_id = self.find_notion_page_id_by_github_url(project.get('github', ''))
                    if recovered_page_id:
                        project['notion_page_id'] = recovered_page_id
                        had_page_id = True
                        recovered_count += 1
                if had_page_id:
                    pending.append((project, category_name))
                else:
                    skipped_count += 1
            projects_to_sync = pending
            print(f"update_only 预检: 待更新 {len(projects_to_sync)} 个,缺少 page_id 跳过 {skipped_count} 个")
            if recovered_count > 0:
                print(f"  ✓ 其中按 GitHub 链接补齐 notion_page_id: {recovered_count} 个")

        for i, (project, category_name) in enumerate(projects_to_sync, 1):
            had_page_id = bool(project.get('notion_page_id', '').strip())

            if not had_page_id:
                recovered_page_id = self.find_notion_page_id_by_github_url(project.get('github', ''))
                if recovered_page_id:
                    print(f"\n[RECOVER] {project.get('id', 'unknown')} 已按 GitHub 链接补齐 notion_page_id")
                    project['notion_page_id'] = recovered_page_id
                    had_page_id = True

            if sync_mode == 'create_only' and had_page_id:
                missing_core = any(
                    [
                        not (project.get('name') or '').strip(),
                        not (project.get('description') or '').strip(),
                        not (project.get('topics') or []),
                    ]
                )
                if missing_core:
                    pass
                else:
                    print(f"\n[SKIP] {project.get('id', 'unknown')} 已存在 notion_page_id,按 create_only 跳过")
                    skipped_count += 1
                    if i < len(projects_with_category):
                        time.sleep(1)
                    continue

            if sync_mode == 'update_only' and not had_page_id:
                print(f"\n[SKIP] {project.get('id', 'unknown')} 缺少 notion_page_id,按 update_only 跳过")
                skipped_count += 1
                if i < len(projects_with_category):
                    time.sleep(1)
                continue
            
            # 同步项目
            page_id, action = self.sync_project(project, category_name)
            
            # 更新配置中的 page_id
            if page_id:
                project['notion_page_id'] = page_id
                if action == "updated":
                    updated_count += 1
                elif action == "created":
                    created_count += 1
                else:
                    # skipped 等情况不记入创建/更新
                    pass
            else:
                if action == "missing_remote":
                    # 确认远端页面不存在且未重建成功时,清空本地脏 page_id
                    project['notion_page_id'] = ""
                failed_count += 1
            
            # API 限速保护
            if i < len(projects_to_sync):
                time.sleep(1)
        
        # 保存更新后的配置
        self.save_projects_config(config, config_file)
        
        # 输出统计
        print("\n" + "="*60)
        print("同步完成!")
        print(f"  ✓ 新创建: {created_count} 个")
        print(f"  ✓ 已更新: {updated_count} 个")
        if skipped_count > 0:
            print(f"  - 已跳过: {skipped_count} 个")
        if failed_count > 0:
            print(f"  ✗ 失败: {failed_count} 个")
        print("="*60 + "\n")


SYNC_MODE_ALIASES = {
    "all": "all",
    "full": "all",
    "both": "all",
    "create_only": "create_only",
    "create": "create_only",
    "new_only": "create_only",
    "only_create": "create_only",
    "update_only": "update_only",
    "update": "update_only",
    "only_update": "update_only",
    "reconcile_only": "reconcile_only",
    "pull_from_notion": "reconcile_only",
    "notion_pull": "reconcile_only",
    "reconcile": "reconcile_only",
}


def normalize_sync_mode(raw_mode: str) -> str:
    """标准化 SYNC_MODE,非法值回退为 all"""
    mode = (raw_mode or "all").strip().lower()
    return SYNC_MODE_ALIASES.get(mode, "all")


def parse_bool_env(raw_value: str, default: bool = False) -> bool:
    """解析布尔环境变量"""
    if raw_value is None:
        return default
    value = str(raw_value).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def resolve_projects_file_path(project_root: Path, config_file: str) -> str:
    """解析配置文件路径,并在常见误配时回退到 data/ 目录"""
    configured = (config_file or "").strip() or DEFAULT_CONFIG_FILENAME
    path = Path(configured)
    if path.is_absolute():
        return configured

    root_candidate = project_root / path
    if root_candidate.exists():
        return configured

    # 常见误配: PROJECTS_FILE=projects.xlsx / projects.json
    if len(path.parts) == 1:
        data_candidate_rel = Path("data") / path.name
        data_candidate_abs = project_root / data_candidate_rel
        if data_candidate_abs.exists():
            print(f"ℹ PROJECTS_FILE={configured} 未命中,自动改用 {data_candidate_rel}")
            return str(data_candidate_rel)

    return configured


def maybe_reconcile_categories_from_notion(
    enabled: bool,
    config: Dict[str, Any],
    notion_token: str,
    config_file: str,
) -> bool:
    """
    按 Notion 页面中的“分类”字段回写本地分类结构。
    返回值表示 config 是否被修改。
    """
    if not enabled:
        return False

    print("\n[预处理] 启用分类反向同步: Notion -> data/projects.xlsx")
    try:
        reconciler = NotionCategoryReconciler(notion_token=notion_token)
        moved_count, created_count, skipped_count = reconcile_projects(config, reconciler)
        print(
            "[预处理] 分类对齐完成: "
            f"移动 {moved_count} 项,新增分类 {created_count} 个,跳过 {skipped_count} 项"
        )
        changed = moved_count > 0 or created_count > 0
        if changed:
            print(f"[预处理] 检测到分类变化,将回写配置文件: {config_file}")
        return changed
    except Exception as e:
        print(f"[预处理] ⚠ 分类反向同步失败,将继续执行主同步: {str(e)}")
        return False


def main():
    """主函数"""
    print("""
╔══════════════════════════════════════════════════════════╗
║         GitHub → Notion 项目同步工具                     ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    # 优先加载项目根目录下的 .env,避免受当前工作目录影响
    project_root = Path(__file__).resolve().parent.parent
    env_file = project_root / '.env'
    if env_file.exists():
        if load_dotenv:
            load_dotenv(dotenv_path=env_file)
        else:
            load_local_env_file(env_file)

    # 从环境变量读取配置
    NOTION_TOKEN = os.environ.get('NOTION_TOKEN', '')
    DATABASE_ID = os.environ.get('NOTION_PROJECTS_DATABASE_ID', '').strip()
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
    SYNC_MODE_RAW = os.environ.get('SYNC_MODE', 'all')
    PROJECTS_FILE_RAW = os.environ.get('PROJECTS_FILE', DEFAULT_CONFIG_FILENAME)
    PROJECTS_FILE = resolve_projects_file_path(project_root, PROJECTS_FILE_RAW)
    SYNC_MODE = normalize_sync_mode(SYNC_MODE_RAW)
    SYNC_FROM_NOTION_FIRST = parse_bool_env(
        os.environ.get('SYNC_FROM_NOTION_FIRST', 'true'),
        default=True,
    )
    SYNC_CATEGORY_FROM_NOTION = parse_bool_env(
        os.environ.get('SYNC_CATEGORY_FROM_NOTION', 'false'),
        default=False,
    )
    
    # 检查必需的配置
    if not NOTION_TOKEN:
        print("❌ 错误: 未设置 NOTION_TOKEN\n")
        print("请设置环境变量:")
        print("  export NOTION_TOKEN='your-token'\n")
        return
    
    if not DATABASE_ID:
        print("❌ 错误: 未设置 NOTION_PROJECTS_DATABASE_ID\n")
        print("请设置环境变量:")
        print("  export NOTION_PROJECTS_DATABASE_ID='your-projects-database-id'\n")
        return

    if (SYNC_MODE_RAW or "all").strip().lower() not in SYNC_MODE_ALIASES:
        print(f"⚠ SYNC_MODE={SYNC_MODE_RAW!r} 无效,已回退为默认模式 all")
    
    # 创建同步器
    syncer = GitHubNotionSync(
        notion_token=NOTION_TOKEN,
        database_id=DATABASE_ID,
        github_token=GITHUB_TOKEN
    )

    # 可选: 先按 Notion “分类”字段对齐本地 categories
    config_file = PROJECTS_FILE
    config = syncer.load_projects_config(config_file)
    config_changed = False

    if SYNC_FROM_NOTION_FIRST:
        print("\n[预处理] 启用 Notion -> 本地项目拉取")
        merge_stats = syncer.merge_notion_projects_into_config(config)
        print(
            "[预处理] 拉取结果: "
            f"Notion {merge_stats['total_notion']} 项, "
            f"新增本地 {merge_stats['inserted']} 项, "
            f"合并 {merge_stats['merged']} 项, "
            f"补字段 {merge_stats['filled_fields']} 处, "
            f"分类移动 {merge_stats['moved_category']} 项, "
            f"新增分类 {merge_stats['created_category']} 个"
        )
        if (
            merge_stats["inserted"] > 0
            or merge_stats["merged"] > 0
            or merge_stats["moved_category"] > 0
            or merge_stats["created_category"] > 0
            or merge_stats["filled_fields"] > 0
        ):
            config_changed = True

    config_changed = maybe_reconcile_categories_from_notion(
        enabled=SYNC_CATEGORY_FROM_NOTION,
        config=config,
        notion_token=NOTION_TOKEN,
        config_file=config_file,
    ) or config_changed

    if SYNC_MODE == "reconcile_only":
        print("\n[模式] reconcile_only: 仅从 Notion 拉取并回写 notion_page_id + 分类")
        stats = syncer.reconcile_local_ids_and_categories_from_notion(config)
        print(
            "[模式] 回写结果: "
            f"补齐 notion_page_id {stats['filled_page_id']} 项, "
            f"清空 notion_page_id {stats['cleared_page_id']} 项, "
            f"分类移动 {stats['moved_category']} 项, "
            f"新增分类 {stats['created_category']} 个, "
            f"Notion 未匹配 {stats['no_match']} 项"
        )
        if stats["duplicate_in_notion"] > 0:
            print(f"[模式] ⚠ 检测到 Notion 同链接重复记录: {stats['duplicate_in_notion']} 项(已取第一条)")
        config_changed = True

    if config_changed:
        syncer.save_projects_config(config, config_file)

    if SYNC_MODE == "reconcile_only":
        print(f"提示: 已完成本地回写,未执行创建/更新同步。配置文件: {config_file}\n")
        return
    
    # 执行同步
    syncer.sync_all_projects(config_file, sync_mode=SYNC_MODE)
    
    print(f"提示: 可以在 {config_file} 中维护项目后再次运行\n")


if __name__ == '__main__':
    main()
