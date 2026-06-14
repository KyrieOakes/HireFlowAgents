# HireFlow

基于 LangGraph 的多 Agent 招聘筛选与面试辅助系统。

## 项目简介

HireFlow 模拟完整招聘筛选流程：JD 分析 → 简历解析 → 候选人匹配评分 → 排序 → 结果展示。

**核心亮点:**
- LangGraph 多 Agent 工作流编排
- 两阶段排序: 关键词粗筛 + LLM 精排
- 7 维度候选人评分体系
- LLM 本地/云端双模式 (一键切换)
- PDF/DOCX 文件上传 + 自动解析
- 评估体系 + 历史对比
- Next.js 前端 (HR/ATS 工作台风格)

## 快速开始

### 1. 环境准备

```bash
# 激活 conda 环境
conda activate hireflowagents

# 安装 Python 依赖 (首次运行)
pip install -r requirements.txt

# 复制环境变量配置
cp .env.example .env
# 编辑 .env 填入你的 API Key
# LLM_CLOUD_API_KEY=你的DeepSeek-API-Key
```

### 2. 启动数据库服务

```bash
# 启动 PostgreSQL + Qdrant
docker compose up -d postgres qdrant

# 确认服务就绪
docker ps --filter "name=hireflow"
# 应该看到 hireflow-postgres 和 hireflow-qdrant 两个容器

# 如需停止服务
docker compose down
```

### 3. 运行 Demo

```bash
# CLI Demo: 用内置示例数据运行完整 Pipeline
python -m app.cli demo

# 用自定义文件运行
python -m app.cli run <岗位文件.txt> <简历文件夹/>
```

### 4. 启动前端

```bash
# 安装前端依赖 (首次运行)
cd frontend && npm install

# 启动 Next.js 开发服务器
npm run dev
# → http://localhost:3000
```

### 5. 启动 API 服务

```bash
# 启动 FastAPI 服务器 (开发模式)
uvicorn app.main:app --reload

# 访问 API 文档
open http://localhost:8000/docs
```

### 6. 运行评估报告

```bash
# 启动 Jupyter Notebook
cd evaluation
jupyter notebook 系统评估报告.ipynb

# 或: 在 VS Code 中打开 .ipynb 文件直接运行
```

## API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/jobs/upload` | 上传岗位描述文本 |
| `POST` | `/jobs/{id}/parse` | 调用 JD Agent 解析 |
| `GET` | `/jobs/{id}` | 获取岗位详情 |
| `DELETE` | `/jobs/{id}` | 删除岗位 |
| `POST` | `/resumes/upload` | 上传简历文本 |
| `POST` | `/resumes/upload-file` | 上传 PDF/DOCX/TXT 文件 |
| `POST` | `/resumes/{id}/parse` | 调用 Resume Agent 解析 |
| `GET` | `/resumes/{id}` | 获取候选人详情 |
| `DELETE` | `/resumes/{id}` | 删除候选人 |
| `POST` | `/jobs/{id}/match?limit=N` | 执行匹配评分 + 排序 (支持 TopN) |
| `GET` | `/jobs/{id}/ranking` | 获取排序结果 |

完整 API 文档: http://localhost:8000/docs (启动后访问)

## 技术栈

| 层级 | 技术 |
|---|---|
| 后端框架 | Python 3.11, FastAPI, LangGraph, LangChain |
| LLM (本地) | LM Studio + hermes-3-llama-3.1-8b |
| LLM (云端) | DeepSeek API + deepseek-v4-pro |
| Embedding | text-embedding-qwen3-embedding-4b (2560维) |
| 数据库 | PostgreSQL 16 (pgvector) |
| 向量数据库 | Qdrant |
| 配置管理 | Pydantic Settings |
| 前端 | Next.js + Tailwind CSS (规划中) |
| 部署 | Docker Compose |

## LLM 模式切换

在 `.env` 文件中设置 `LLM_MODE`:

```bash
# 本地 LM Studio (免费, 开发用)
LLM_MODE=local

# 云端 DeepSeek API (生产级, 需 API Key)
LLM_MODE=cloud
LLM_CLOUD_API_KEY=sk-xxxxxxxx
```

## 测试数据

项目内置 3 份示例简历 + 1 个 AI 工程师 JD (在 `app/cli.py` 的 `run_demo()` 中)。

### 测试数据说明

| 候选人 | 背景 | 匹配度预期 |
|---|---|---|
| 李明 | AI 硕士, LangChain/RAG 项目经验 | 高分 (Strong Match) |
| 王芳 | Java 后端, 无 AI 经验 | 中等 (Medium Match) |
| 张伟 | 数据科学硕士, 有简历筛选项目 | 较高 (Strong Match) |

### 添加更多测试数据

1. 在 `data/resumes/` 下创建 `.txt` 或 `.md` 格式的简历文件
2. 在 `data/jobs/` 下创建 JD 文件
3. 运行: `python -m app.cli run data/jobs/你的JD.txt data/resumes/`

未来会支持 PDF/DOCX 文件上传 (通过 API)。
测试数据来源: 由 LLM 生成的 synthetic resumes (非真实简历).

## 项目结构

```
HireFlowAgents/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── cli.py               # 命令行 Demo 工具
│   ├── api/                  # 3 个路由模块 (jobs/resumes/matching)
│   ├── agents/               # 4 个 Agent (jd/resume/match/ranking)
│   ├── graph/                # LangGraph 工作流 (state/nodes/workflow)
│   ├── schemas/              # Pydantic 数据模型
│   ├── services/             # 5 个服务 (llm/embedding/vector/document/rag)
│   ├── database/             # PostgreSQL ORM (models/session/crud)
│   └── utils/                # config + logger
├── evaluation/               # 评估脚本 + Notebook
├── data/                     # 测试数据 (JD + 简历)
│   ├── jobs/                 # 岗位描述文件
│   └── resumes/              # 简历文件
├── logs/                     # 项目文档
│   ├── HireFlow_项目计划书.md
│   ├── 技术栈选择原因.md
│   ├── MVPs/                 # MVP 阶段规划
│   └── 开发日志/             # 开发日志
├── docker-compose.yml        # PostgreSQL + Qdrant + API
├── requirements.txt          # Python 依赖
├── .env.example              # 环境变量模板
└── README.md
```

## 常用命令速查

```bash
conda activate hireflowagents          # 激活环境
docker compose up -d postgres qdrant   # 启动数据库
docker compose down                    # 停止数据库
python -m app.cli demo                 # 运行 Demo
uvicorn app.main:app --reload          # 启动 API
```
