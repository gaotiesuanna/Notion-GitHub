# GitHub 项目汇总页面 - 实现方案

## 📋 方案概述

基于你的需求(自动同步 GitHub 项目信息到 Notion,展示统计数据),我提供以下完整方案:

---

## 🏗️ 架构设计

```
┌─────────────────┐
│  projects.json  │  ← 项目配置文件(你提供的格式)
└────────┬────────┘
         │
         ↓
┌─────────────────────────┐
│  Python 同步脚本        │
│  - 读取 JSON 配置       │
│  - 调用 GitHub API      │  ← 获取实时数据(Stars/Forks/活跃度)
│  - 更新 Notion 数据库   │
└────────┬────────────────┘
         │
         ↓
┌─────────────────────────┐
│  Notion 数据库          │  ← 存储和展示项目信息
│  - 项目名称             │
│  - GitHub 链接          │
│  - Stars/Forks 统计     │
│  - 技术标签             │
│  - 最后更新时间         │
│  - 活跃度指标           │
└─────────────────────────┘
         │
         ↓
┌─────────────────────────┐
│  Notion 页面展示        │  ← 可视化界面
│  - 表格视图             │
│  - 画廊视图             │
│  - 看板视图             │
│  - 嵌入 GitHub 徽章     │
└─────────────────────────┘
```

---

## 📁 文件结构

```
github-notion-sync/
├── projects.json              # 项目配置文件(你的格式)
├── sync_github_to_notion.py   # 主同步脚本
├── requirements.txt           # Python 依赖
├── .env.example              # 环境变量模板
├── README.md                 # 使用文档
└── notion_template.md        # Notion 数据库结构说明
```

---

## 🎯 核心功能

### 1. 配置文件 (projects.json)
使用你提供的 JSON 格式:
```json
{
  "projects": [
    {
      "id": "vuejs",
      "name": "Vue.js",
      "description": "渐进式JavaScript框架",
      "github": "https://github.com/vuejs/vue",
      "topics": ["frontend", "framework", "vue"],
      "notion_page_id": ""  // 自动填充
    }
  ]
}
```

**特点:**
- ✅ 人工维护项目列表
- ✅ 自动保存 Notion page_id 映射
- ✅ 支持自定义标签和分类

### 2. Python 同步脚本
```python
功能:
1. 读取 projects.json
2. 调用 GitHub API 获取实时数据
3. 创建/更新 Notion 页面
4. 回写 notion_page_id 到 JSON
```

**获取的实时数据:**
- ⭐ Stars 数量
- 🍴 Forks 数量
- 👁️ Watchers 数量
- 🐛 Open Issues 数量
- 📝 项目描述
- 🏷️ Topics 标签
- 🕒 最后更新时间
- 🕒 最后推送时间
- 📜 开源许可证
- 💻 主要编程语言
- 📦 是否归档

### 3. Notion 数据库结构

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 项目名称 | Title | 主标题 |
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
| 状态 | Select | 活跃/已归档 |

---

## 🚀 使用流程

### Step 1: 准备 Notion
1. 创建 Notion Integration
   - 访问: https://www.notion.so/my-integrations
   - 创建新 Integration,获取 Token

2. 创建 Notion 数据库
   - 新建一个 Database (Full Page)
   - 按照上面的结构添加属性
   - 将 Integration 添加到数据库 (Share → Invite)

3. 获取 Database ID
   - 从数据库 URL 复制: `https://notion.so/xxx/{database_id}?v=...`

### Step 2: 配置脚本
```bash
# 安装依赖
pip install requests python-dotenv

# 设置环境变量
export NOTION_TOKEN="your_notion_token"
export NOTION_DATABASE_ID="your_database_id"
export GITHUB_TOKEN="your_github_token"  # 可选,提高 API 限制
```

### Step 3: 编辑 projects.json
```json
{
  "projects": [
    {
      "id": "vuejs",
      "name": "Vue.js",
      "github": "https://github.com/vuejs/vue",
      "topics": ["frontend"],
      "notion_page_id": ""
    }
  ]
}
```

### Step 4: 运行同步
```bash
python sync_github_to_notion.py
```

**运行结果:**
```
============================================================
GitHub → Notion 同步工具
============================================================
✓ 成功加载配置文件: projects.json
  共 3 个项目

[vuejs] Vue.js
  ✓ GitHub API: vuejs/vue (⭐ 204,000)
  ✓ Notion 页面已创建: Vue.js

✓ 配置文件已更新: projects.json
============================================================
同步完成!
  ✓ 新创建: 1 个
  ✓ 已更新: 2 个
============================================================
```

### Step 5: 在 Notion 中查看
- 所有项目自动显示在数据库中
- 可以切换不同视图 (表格/画廊/看板)
- 实时统计数据已同步

---

## 🎨 Notion 展示优化

### 1. 嵌入 GitHub 徽章
在 Notion 页面中添加:
```markdown
![Stars](https://img.shields.io/github/stars/vuejs/vue?style=social)
![Forks](https://img.shields.io/github/forks/vuejs/vue?style=social)
![License](https://img.shields.io/github/license/vuejs/vue)
```

### 2. 创建不同视图
- **表格视图**: 列表展示所有项目
- **画廊视图**: 卡片式展示,按 Stars 排序
- **看板视图**: 按技术栈分组 (Frontend/Backend/Tools)
- **时间线视图**: 按最后更新时间排序

### 3. 公式字段示例
在 Notion 中添加公式字段计算活跃度:

**活跃度评分** (Formula):
```
if(dateBetween(now(), prop("最后推送"), "days") < 7, "🔥 非常活跃",
  if(dateBetween(now(), prop("最后推送"), "days") < 30, "✅ 活跃",
    if(dateBetween(now(), prop("最后推送"), "days") < 90, "⚠️ 一般", "❌ 不活跃")))
```

**热度指数** (Formula):
```
prop("Stars") + prop("Forks") * 2 + prop("Watchers") * 0.5
```

---

## ⚙️ 自动化方案

### 方案 A: 定时任务 (推荐)
```bash
# Linux/macOS - Cron
# 每天早上 9 点执行
0 9 * * * cd /path/to/project && python sync_github_to_notion.py

# Windows - Task Scheduler
# 创建计划任务,每天执行脚本
```

### 方案 B: GitHub Actions (进阶)
```yaml
# .github/workflows/sync-to-notion.yml
name: Sync to Notion
on:
  schedule:
    - cron: '0 9 * * *'  # 每天 9:00 UTC
  workflow_dispatch:

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install requests
      - run: python sync_github_to_notion.py
        env:
          NOTION_TOKEN: ${{ secrets.NOTION_TOKEN }}
          NOTION_DATABASE_ID: ${{ secrets.DATABASE_ID }}
          GITHUB_TOKEN: ${{ secrets.GH_TOKEN }}
```

---

## 📊 扩展功能

### 1. 趋势分析
- 记录每次同步的 Stars 数量
- 在 Notion 中绘制增长曲线
- 识别快速增长的项目

### 2. 批量操作
```python
# 批量添加 awesome-xxx 列表中的项目
# 批量导入 GitHub Star 列表
# 从 GitHub Collections 导入
```

### 3. 通知提醒
```python
# Stars 达到里程碑时发送通知
# 项目有新 Release 时提醒
# 长期未更新的项目警告
```

---

## ⚠️ 注意事项

### GitHub API 限制
- **未认证**: 60 次/小时
- **已认证**: 5000 次/小时
- **建议**: 使用 Personal Access Token

### Notion API 限制
- **限速**: 3 次/秒
- **建议**: 在请求之间添加 sleep(1)

### 最佳实践
1. 定期备份 projects.json
2. 为重要项目设置优先级
3. 使用 Git 管理配置文件
4. 测试前先用小数据集

---

## 🔧 技术栈

- **Python 3.7+**: 主要开发语言
- **requests**: HTTP 请求库
- **GitHub REST API v3**: 获取仓库数据
- **Notion API 2022-06-28**: 数据库操作
- **JSON**: 配置文件格式

---

## 📚 参考资源

- [Notion API 文档](https://developers.notion.com/)
- [GitHub REST API 文档](https://docs.github.com/rest)
- [Notion 数据库最佳实践](https://www.notion.so/help/guides/creating-a-database)

---

## 🎯 下一步

接下来我将为你创建:
1. ✅ 完整的 Python 同步脚本
2. ✅ projects.json 配置模板
3. ✅ requirements.txt 依赖文件
4. ✅ .env 环境变量模板
5. ✅ README.md 使用文档
6. ✅ Notion 数据库结构说明

你想先看哪个部分的详细代码?
