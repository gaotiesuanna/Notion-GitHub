# 🚀 快速开始指南 - 同步 GitHub 项目到 Notion

## 📋 前提条件

你需要准备:
- ✅ Notion Integration Token
- ✅ Notion Database ID
- ✅ Python 3.7+
- ⭐ GitHub Token (可选,但推荐)

---

## 🎯 完整操作步骤

### 步骤 1: 设置 Notion (5 分钟)

#### 1.1 创建 Integration
1. 访问: https://www.notion.so/my-integrations
2. 点击 **"+ New integration"**
3. 填写名称: `GitHub Sync Bot`
4. 点击 **Submit**
5. 复制 **Token**（保存为环境变量，不要写入代码）

#### 1.2 创建数据库
1. 在 Notion 中创建新页面
2. 输入 `/table` 创建数据库
3. 添加以下字段:

| 字段名 | 类型 |
|--------|------|
| 项目名称 | Title (默认) |
| GitHub 链接 | URL |
| 描述 | Text |
| Stars | Number |
| Forks | Number |
| Watchers | Number |
| Open Issues | Number |
| 主要语言 | Select |
| 技术标签 | Multi-select |
| 最后更新 | Date |
| 最后推送 | Date |
| 作者 | Text |
| 许可证 | Select |
| 状态 | Select |

#### 1.3 连接 Integration 到数据库
1. 点击数据库右上角 **三点菜单 (...)**
2. 选择 **"Connections"**
3. 找到并添加 `GitHub Sync Bot`

#### 1.4 获取 Database ID
从数据库页面 URL 复制:
```
https://www.notion.so/workspace/a1b2c3d4e5f67890abcdef1234567890?v=...
                                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                      这就是 Database ID
```

---

### 步骤 2: 安装和配置 (2 分钟)

#### 2.1 安装依赖
```bash
pip install requests python-dotenv
```

或使用 requirements.txt:
```bash
pip install -r requirements.txt
```

#### 2.2 配置环境变量

**方式 A: 使用 .env 文件 (推荐)**
```bash
# 复制模板
cp .env.example .env

# 编辑 .env 文件
nano .env
```

填入你的配置:
```bash
NOTION_TOKEN=your_notion_token
NOTION_DATABASE_ID=a1b2c3d4e5f67890abcdef1234567890
GITHUB_TOKEN=your_github_token  # 可选
```

**方式 B: 直接设置环境变量**
```bash
export NOTION_TOKEN="your_notion_token"
export NOTION_DATABASE_ID="a1b2c3d4e5f67890abcdef1234567890"
export GITHUB_TOKEN="your_github_token"  # 可选
```

---

### 步骤 3: 添加项目到配置文件 (1 分钟)

编辑 `projects.json`:

```json
{
  "projects": [
    {
      "id": "crewai",
      "name": "CrewAI",
      "description": "Framework for orchestrating role-playing, autonomous AI agents",
      "github": "https://github.com/crewAIInc/crewAI",
      "topics": ["ai", "agents", "framework"],
      "notion_page_id": ""
    }
  ]
}
```

**字段说明:**
- `id`: 项目唯一标识 (自己命名)
- `name`: 项目名称
- `description`: 简短描述 (可选)
- `github`: GitHub 仓库 URL ⭐ **必填**
- `topics`: 技术标签 (可选)
- `notion_page_id`: 留空,脚本会自动填充

---

### 步骤 4: 运行同步 (30 秒)

```bash
python sync.py
```

**预期输出:**
```
╔══════════════════════════════════════════════════════════╗
║         GitHub → Notion 项目同步工具                      ║
╚══════════════════════════════════════════════════════════╝

✓ 成功加载配置文件: projects.json
  共 1 个项目

开始同步 1 个项目...

============================================================
[crewai] CrewAI
============================================================
  ✓ GitHub API: crewAIInc/crewAI (⭐ 15,234)
  ✓ Notion 页面已创建

✓ 配置文件已更新: projects.json
============================================================
同步完成!
  ✓ 新创建: 1 个
  ✓ 已更新: 0 个
============================================================
```

---

### 步骤 5: 查看 Notion 中的结果

打开你的 Notion 数据库,你会看到:
- ✅ CrewAI 项目已添加
- ✅ Stars、Forks 等统计信息已同步
- ✅ 技术标签已添加
- ✅ 最后更新时间已记录

---

## 📦 添加更多项目

### 方法 1: 编辑 projects.json

```json
{
  "projects": [
    {
      "id": "crewai",
      "name": "CrewAI",
      "github": "https://github.com/crewAIInc/crewAI",
      "notion_page_id": "xxx"
    },
    {
      "id": "langchain",
      "name": "LangChain",
      "github": "https://github.com/langchain-ai/langchain",
      "topics": ["ai", "llm"],
      "notion_page_id": ""
    },
    {
      "id": "autogen",
      "name": "AutoGen",
      "github": "https://github.com/microsoft/autogen",
      "topics": ["ai", "agents"],
      "notion_page_id": ""
    }
  ]
}
```

然后再次运行:
```bash
python sync.py
```

### 方法 2: 批量添加

可以创建一个辅助脚本:

```python
# add_project.py
import json

def add_project(github_url, name=None, topics=None):
    """添加新项目到配置"""
    with open('projects.json', 'r') as f:
        config = json.load(f)
    
    # 从 URL 提取 ID
    repo_id = github_url.rstrip('/').split('/')[-1].lower()
    
    project = {
        "id": repo_id,
        "name": name or repo_id,
        "github": github_url,
        "topics": topics or [],
        "notion_page_id": ""
    }
    
    config['projects'].append(project)
    
    with open('projects.json', 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"✓ 已添加: {name or repo_id}")

# 使用示例
add_project("https://github.com/openai/gpt-4", "GPT-4", ["ai", "llm"])
```

---

## 🔄 定时自动同步

### 使用 Cron (Linux/macOS)

```bash
# 编辑 crontab
crontab -e

# 添加以下行 (每天早上 9 点执行)
0 9 * * * cd /path/to/github-notion-sync && python sync.py >> sync.log 2>&1
```

### 使用 Windows 任务计划程序

1. 打开 **任务计划程序**
2. 创建基本任务
3. 设置触发器: 每天
4. 设置操作: 启动程序
   - 程序: `python`
   - 参数: `C:\path\to\sync.py`

---

## 🎨 Notion 优化建议

### 1. 创建不同视图

**表格视图**: 显示所有详细信息
**画廊视图**: 卡片式展示,按 Stars 排序
**看板视图**: 按技术栈分组

### 2. 添加公式字段

**活跃度评分**:
```
if(dateBetween(now(), prop("最后推送"), "days") < 7, "🔥 非常活跃",
  if(dateBetween(now(), prop("最后推送"), "days") < 30, "✅ 活跃", "⚠️ 一般"))
```

**热度指数**:
```
prop("Stars") + prop("Forks") * 2
```

### 3. 嵌入 GitHub 徽章

在项目页面添加:
```markdown
![Stars](https://img.shields.io/github/stars/crewAIInc/crewAI?style=social)
![Forks](https://img.shields.io/github/forks/crewAIInc/crewAI?style=social)
```

---

## ❓ 常见问题

### Q: 同步会覆盖我在 Notion 中的手动修改吗?
A: 只会更新 GitHub 相关的字段 (Stars、Forks 等),不会覆盖你添加的自定义内容。

### Q: 可以同步私有仓库吗?
A: 可以!需要设置 GitHub Token,并确保 Token 有访问私有仓库的权限。

### Q: GitHub API 有限制吗?
A: 
- 未认证: 60 次/小时
- 已认证: 5000 次/小时
- 建议使用 GitHub Token

### Q: 如何获取 GitHub Token?
A:
1. 访问: https://github.com/settings/tokens
2. 点击 "Generate new token (classic)"
3. 选择权限: `repo` (访问仓库信息)
4. 复制生成的 Token

### Q: 出错怎么办?
A: 检查:
1. Token 和 Database ID 是否正确
2. Integration 是否已连接到数据库
3. 数据库字段是否完整
4. 运行测试脚本验证连接

---

## 🎉 完成!

现在你已经可以:
- ✅ 自动同步 GitHub 项目信息到 Notion
- ✅ 跟踪项目的 Stars、Forks 等统计数据
- ✅ 监控项目的活跃度
- ✅ 管理和组织你关注的开源项目

有问题随时查看文档或提问! 🚀
