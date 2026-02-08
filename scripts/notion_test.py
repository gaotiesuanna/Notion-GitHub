import os
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def load_local_env_file(env_path: Path):
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


project_root = Path(__file__).resolve().parent.parent
env_file = project_root / ".env"
if env_file.exists():
    if load_dotenv:
        load_dotenv(dotenv_path=env_file)
    else:
        load_local_env_file(env_file)

notion_token = os.environ.get("NOTION_TOKEN", "").strip()
database_id = os.environ.get("NOTION_DATABASE_ID", "").strip()

if not notion_token or not database_id:
    print("❌ 缺少环境变量: NOTION_TOKEN / NOTION_DATABASE_ID")
    raise SystemExit(1)

headers = {
    "Authorization": f"Bearer {notion_token}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

url = f"https://api.notion.com/v1/databases/{database_id}"
response = requests.get(url, headers=headers, timeout=10)

if response.status_code == 200:
    print("✅ 连接成功!")
    title = response.json().get("title", [])
    db_name = title[0].get("text", {}).get("content", "未命名数据库") if title else "未命名数据库"
    print(f"数据库名称: {db_name}")
else:
    print(f"❌ 连接失败: {response.status_code}")
    print(response.text)
