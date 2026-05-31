# HireFlow

基于 LangGraph 的多 Agent 招聘筛选与面试辅助系统。

## 项目简介

HireFlow 是一个模拟完整招聘流程的 AI 系统，使用 LangGraph 编排多个专业 Agent 协同工作。

**核心功能:**
- 岗位描述(JD)结构化分析
- 简历批量解析与候选人画像构建
- 基于 RAG 证据的候选人匹配评分
- 候选人排序与 Shortlist 推荐
- 定制化面试问题生成
- 面试后的候选人评价
- HR 邮件草稿生成 (人工审核后发送)

## 技术栈

- **后端**: Python, FastAPI, LangGraph, LangChain
- **前端**: React / Next.js, Tailwind CSS
- **向量数据库**: Chroma (MVP)
- **数据库**: SQLite (MVP) → PostgreSQL
- **部署**: Docker

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 OPENAI_API_KEY

# 3. 启动后端
uvicorn app.main:app --reload

# 4. 访问 API 文档
open http://localhost:8000/docs
```

## 项目结构

见 [PROJECT_PLAN.md](logs/HireFlow_项目计划书.md) 中的完整规划。
