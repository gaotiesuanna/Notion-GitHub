# GitHub → Notion 项目同步工具

自动同步 GitHub 项目信息到 Notion 数据库,跟踪 Stars、Forks、活跃度等统计数据。

## ✨ 功能特点

- 🔄 **自动同步** GitHub 仓库信息到 Notion
- ⭐ **实时统计** Stars、Forks、Watchers、Issues 数量
- 🏷️ **技术标签** 自动同步 GitHub Topics
- 📅 **活跃度追踪** 记录最后更新和推送时间
- 💾 **配置管理** 基于 JSON 的项目配置
- 🔐 **安全** 支持私有仓库 (使用 GitHub Token)

## 📦 文件说明

```
github-notion-sync/
├── sync.py              # 主同步脚本
├── projects.json        # 项目配置文件
├── requirements.txt     # Python 依赖
├── .env.example         # 环境变量模板
├── QUICKSTART.md        # 快速开始指南 ⭐ 重要
├── SOLUTION.md          # 完整方案说明
├── NOTION_SETUP_GUIDE.md    # Notion 设置教程
└── GET_DATABASE_ID.md   # Database ID 获取指南
```

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置环境变量
```bash
export NOTION_TOKEN="secret_xxxxxxxxxxxxx"
export NOTION_DATABASE_ID="your_database_id"
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxx"  # 可选
```

### 3. 编辑 projects.json
```json
{
  "projects": [
    {
      "id": "crewai",
      "name": "CrewAI",
      "github": "https://github.com/crewAIInc/crewAI",
      "topics": ["ai", "agents"],
      "notion_page_id": ""
    }
  ]
}
```

### 4. 运行同步
```bash
python sync.py
```

## 📚 详细文档

- **[快速开始指南](QUICKSTART.md)** - 5 分钟上手教程
- **[完整方案说明](SOLUTION.md)** - 架构和功能详解
- **[Notion 设置教程](NOTION_SETUP_GUIDE.md)** - Integration 配置
- **[Database ID 获取](GET_DATABASE_ID.md)** - ID 提取方法

## 💡 使用示例

### 示例 1: 同步单个项目
```json
{
  "projects": [
    {
      "id": "crewai",
      "github": "https://github.com/crewAIInc/crewAI",
      "notion_page_id": ""
    }
  ]
}
```

### 示例 2: 同步多个项目
```json
{
  "projects": [
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

## 🔧 配置说明

### 环境变量

| 变量名 | 必需 | 说明 |
|--------|------|------|
| `NOTION_TOKEN` | ✅ | Notion Integration Token |
| `NOTION_DATABASE_ID` | ✅ | Notion 数据库 ID |
| `GITHUB_TOKEN` | ⭐ | GitHub Token (推荐,提高 API 限制) |

### projects.json 字段

| 字段 | 必需 | 说明 |
|------|------|------|
| `id` | ✅ | 项目唯一标识 |
| `name` | ⭐ | 项目名称 |
| `github` | ✅ | GitHub 仓库 URL |
| `description` | ⭐ | 项目描述 |
| `topics` | ⭐ | 技术标签数组 |
| `notion_page_id` | 🤖 | 自动生成,留空即可 |

## 📊 Notion 数据库结构

需要在 Notion 中创建以下字段:

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 项目名称 | Title | 项目名称 |
| GitHub 链接 | URL | 仓库链接 |
| 描述 | Text | 项目描述 |
| Stars | Number | ⭐ 数量 |
| Forks | Number | 🍴 数量 |
| Watchers | Number | 👁️ 数量 |
| Open Issues | Number | 🐛 数量 |
| 主要语言 | Select | 编程语言 |
| 技术标签 | Multi-select | Topics |
| 最后更新 | Date | 更新时间 |
| 最后推送 | Date | 推送时间 |
| 作者 | Text | 仓库所有者 |
| 许可证 | Select | 开源协议 |
| 状态 | Select | 活跃状态 |

## 🎨 Notion 优化建议

### 创建多种视图
- **表格视图**: 完整数据展示
- **画廊视图**: 卡片式,按 Stars 排序
- **看板视图**: 按技术栈分组

### 添加公式字段
```javascript
// 活跃度
if(dateBetween(now(), prop("最后推送"), "days") < 7, "🔥", "✅")

// 热度指数
prop("Stars") + prop("Forks") * 2
```

## 🔄 自动化

### Cron (Linux/macOS)
```bash
0 9 * * * cd /path/to/project && python sync.py
```

### Windows 任务计划程序
创建计划任务,每天执行 `python sync.py`

## ❓ 常见问题

**Q: 同步频率建议?**
A: 每天 1-2 次即可,GitHub 数据更新不频繁。

**Q: 支持私有仓库吗?**
A: 支持!需要配置 GitHub Token。

**Q: API 限制怎么办?**
A: 使用 GitHub Token 可将限制提升至 5000 次/小时。

**Q: 同步会覆盖手动修改吗?**
A: 不会,只更新 GitHub 相关字段。

## 🛠️ 技术栈

- Python 3.7+
- requests
- GitHub REST API v3
- Notion API 2022-06-28

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request!

## 📞 支持

遇到问题?
1. 查看 [QUICKSTART.md](QUICKSTART.md)
2. 查看 [常见问题](#-常见问题)
3. 提交 Issue

---

Made with ❤️ for GitHub and Notion users
# Notion-GitHub
