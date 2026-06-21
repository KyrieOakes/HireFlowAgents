# HireFlow

基于 LangGraph 的多 Agent 招聘筛选与面试辅助系统。

## 项目简介

HireFlow 模拟完整招聘流程：JD 分析 → 简历解析 → 粗筛 → LLM 精排 → 面试问题 → 面试评价 → 邮件草稿。

**核心亮点:**
- 7 个专业 Agent (JD/Resume/Match/Ranking/Interview/Evaluation/Email)
- 两阶段排序: 关键词粗筛 + LLM 精排 (ThreadPool 并行)
- RAG 证据检索 (简历向量化 + Qdrant 语义搜索)
- Human-in-the-loop 审核 (interrupt/resume)
- LLM 本地/云端双模式 (一键切换)
- PDF/DOCX 文件上传 + 自动解析 + 自动命名
- 前端产品化体验: 毛玻璃工作台、详情弹层、局部 loading、连续解析
- LLM 稳定性兜底: 简历语义错位修复、匹配输出截断兜底评分
- 49 个测试 (0 failures)
- Next.js 前端 (HR/ATS 工作台风格)

## 快速开始

### 1. 环境准备

```bash
conda activate hireflowagents
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env: LLM_MODE=local 或 cloud, 填入 API Key
```

### 2. 启动数据库

```bash
docker compose up -d postgres qdrant        # 启动
docker ps --filter "name=hireflow"          # 确认
docker compose down                         # 停止
```

### 3. 启动后端 API

```bash
uvicorn app.main:app --reload               # → http://localhost:8000
open http://localhost:8000/docs             # API 文档
```

### 4. 启动前端

```bash
cd frontend && npm install                  # 首次
npm run dev                                 # → http://localhost:3000
```

### 5. CLI Demo

```bash
python -m app.cli demo                      # 内置示例数据
python -m app.cli run <JD.txt> <简历目录>    # 自定义数据
```

### 6. 评估报告

```bash
cd evaluation
jupyter notebook 系统评估报告.ipynb         # 8 个 Cell
python run_eval.py                          # 自动化脚本
```

### 7. 测试

```bash
pytest tests/                               # 49 tests
pytest tests/ -v                            # 详细
```

## 系统 Agent

| Agent | 职责 | 输出 |
|---|---|---|
| JD Agent | 解析岗位描述 | 结构化 JD + 评分 Rubric |
| Resume Agent | 解析简历 | 候选人画像 (教育/技能/项目/经历) |
| Match Agent | 匹配评分 | 7 维度分数 + 证据 |
| Ranking Agent | 排序 | 排名表 + Shortlist + 解释 |
| Interview Agent | 面试问题 | 4 类定制化问题 (技术/项目/行为/风险) |
| Evaluation Agent | 面试评价 | 技术/沟通/问题解决 + 推荐建议 |
| Email Agent | 邮件草稿 | 面试邀请/拒信/跟进/下一轮 |

## API 端点

### 岗位与简历
| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/jobs/upload` | 上传岗位描述 |
| `POST` | `/jobs/{id}/parse` | JD Agent 解析 |
| `GET` | `/jobs/{id}` | 岗位详情 |
| `DELETE` | `/jobs/{id}` | 删除岗位 |
| `POST` | `/resumes/upload` | 上传简历文本 |
| `POST` | `/resumes/upload-file` | 上传 PDF/DOCX/TXT |
| `POST` | `/resumes/{id}/parse` | Resume Agent 解析 (自动 RAG 索引) |
| `GET` | `/resumes/{id}` | 候选人详情 |
| `DELETE` | `/resumes/{id}` | 删除候选人 |

### 匹配与排名
| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/jobs/{id}/match?limit=N` | 两阶段匹配 (粗筛+精排) |
| `GET` | `/jobs/{id}/ranking?limit=N` | 排名结果 |
| `GET` | `/jobs/{id}/candidates/{id}/detail` | 详细评分 |

### 面试、评价、邮件
| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/jobs/{id}/candidates/{id}/questions` | 生成面试问题 |
| `GET` | `/jobs/{id}/candidates/{id}/questions` | 获取问题列表 |
| `POST` | `/jobs/{id}/candidates/{id}/evaluate` | 提交面试评价 |
| `GET` | `/jobs/{id}/candidates/{id}/evaluation` | 获取评价 |
| `POST` | `/jobs/{id}/candidates/{id}/email-draft` | 生成邮件草稿 |
| `GET` | `/jobs/{id}/candidates/{id}/email-draft` | 获取草稿列表 |
| `POST` | `/email-drafts/{id}/approve` | 批准草稿 (不发送) |

### 工作流
| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/workflow/run` | 启动 LangGraph 工作流 (含 HITL) |
| `POST` | `/workflow/{id}/resume` | 人工审核后继续 |
| `GET` | `/workflow/{id}/state` | 查看工作流状态 |

## 技术栈

| 层级 | 技术 |
|---|---|
| 后端 | Python 3.11, FastAPI, LangGraph, LangChain |
| LLM 本地 | LM Studio + hermes-3-llama-3.1-8b |
| LLM 云端 | DeepSeek API + deepseek-v4-flash |
| Embedding | text-embedding-qwen3-embedding-4b (2560维) |
| 数据库 | PostgreSQL 16 |
| 向量库 | Qdrant |
| 前端 | Next.js 14 + TypeScript + Tailwind CSS |
| 测试 | pytest (49 tests), SQLite 内存库, FastAPI TestClient |
| 配置 | Pydantic Settings + .env |
| 部署 | Docker Compose |

## 项目结构

```
HireFlowAgents/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── cli.py               # CLI Demo
│   ├── api/                  # 6 个路由 (jobs/resumes/matching/interview/evaluation/workflow)
│   ├── agents/               # 7 个 Agent
│   ├── graph/                # LangGraph (state/nodes/workflow + HITL)
│   ├── schemas/              # Pydantic 模型
│   ├── services/             # 6 个服务 (llm/embedding/vector/document/rag/pre_screening)
│   ├── database/             # ORM + CRUD (7 表)
│   └── utils/                # config + logger
├── frontend/                 # Next.js (4 页面)
├── evaluation/               # Notebook + 评估脚本 + reports
├── tests/                    # 49 tests (Agent/CRUD/API/E2E)
├── data/                     # 测试数据
├── logs/                     # 项目文档 + 开发日志
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 安全与合规

- Agent 只生成建议/草稿，不做最终决定
- `requires_human_review` / `requires_human_approval` = true
- 邮件 `status="draft"`，审核只改状态，不发送
- 不编造时间/地点/薪资/录用承诺
- API Key 从 `.env` 读取，不硬编码

## 稳定性设计

- Resume Agent: 姓名、邮箱、电话、教育、项目、技能优先从原文规则解析，LLM 输出作为补充，避免章节标题或乱码进入画像。
- Match Agent: prompt 自动截断，输出强制简洁；单个候选人 LLM 精排失败时返回规则兜底评分，不让 Top N 匹配整体失败。
- 前端交互: 简历解析使用单卡片 loading + 后台同步，连续解析多个候选人时页面不会白屏。
- 详情弹层: 岗位、简历、匹配详情统一高层级弹窗和遮罩滚动，避免被导航遮挡。

## 常用命令

```bash
conda activate hireflowagents
docker compose up -d postgres qdrant
uvicorn app.main:app --reload
cd frontend && npm run dev
python -m app.cli demo
pytest tests/
```
