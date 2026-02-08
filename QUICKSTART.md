# 快速开始 - GitHub -> Notion 同步

## 1) 准备

需要以下信息：
- `NOTION_TOKEN`
- `NOTION_DATABASE_ID`
- （可选）`GITHUB_TOKEN`

## 2) 安装依赖

```bash
pip install -r requirements.txt
```

或：

```bash
make install
```

## 3) 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，至少填写：

```bash
NOTION_TOKEN=your_notion_token
NOTION_DATABASE_ID=your_database_id
GITHUB_TOKEN=your_github_token_optional
PROJECTS_FILE=data/projects.xlsx
SYNC_MODE=all
SYNC_CATEGORY_FROM_NOTION=false
```

## 4) 维护项目配置

主配置文件：`data/projects.xlsx`

- Sheet `categories`: `id`, `name`, `icon`, `order`
- Sheet `projects`: `category_id`, `id`, `name`, `description`, `github`, `topics`, `notion_page_id`, `order`

## 5) 运行同步

```bash
make sync
```

或：

```bash
python scripts/sync.py
```

## 6) 分类反向同步（可选）

仅预览：

```bash
make reconcile
```

写入配置：

```bash
make reconcile-apply
```

## 常用命令

Notion 连接测试：

```bash
make test
```
