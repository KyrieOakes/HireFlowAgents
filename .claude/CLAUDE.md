# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HireFlow is a LangGraph-based multi-agent recruitment screening and interview assistant system. It models the full recruitment pipeline — JD analysis, resume parsing, candidate matching, ranking, interview question generation, interview evaluation, and HR email drafting — as a controlled multi-agent workflow with human-in-the-loop checkpoints.

## Tech Stack (Finalized 2026-05-31)

- **Backend**: Python 3.11, FastAPI, LangGraph, LangChain, Pydantic
- **LLM**: DeepSeek API (cloud) + LM Studio (local) — dual mode, OpenAI-compatible
- **Embedding**: DeepSeek (cloud) + LM Studio (local) — same dual-mode design
- **Structured Output**: LangChain `with_structured_output()` + Pydantic
- **Frontend**: Next.js, Tailwind CSS
- **Vector DB**: Qdrant
- **Database**: PostgreSQL (with pgvector for future hybrid search)
- **LangGraph Persistence**: PostgresSaver
- **Config**: Pydantic Settings
- **PDF Parsing**: LangChain Document Loaders (PyMuPDF backend) + RecursiveCharacterTextSplitter
- **Infrastructure**: Docker Compose (API + PostgreSQL + Qdrant)

## Architecture

The system has six layers:

1. **Document Input & Preprocessing** — Load and extract text from PDF/DOCX/TXT; chunk for embedding
2. **Information Extraction** — LLM-powered extraction of structured JSON from unstructured text, governed by Pydantic schemas
3. **Retrieval (RAG)** — Embed resume/JD chunks into a vector DB; retrieve evidence for match claims
4. **Multi-Agent Workflow (core)** — LangGraph StateGraph orchestrates 7 agents (see below)
5. **API** — FastAPI REST endpoints for all operations
6. **Frontend** — Dashboard, job detail, candidate ranking, interview, and email draft pages

### LangGraph Workflow

Two main workflows share a typed `HiringState` (see `app/graph/state.py`):

**Pre-interview screening:**
```
START → JD Agent → Resume Agent → Resume Validation → Evidence Retrieval → Match Agent → Ranking Agent → Human Review → END
```

**Interview support:**
```
START → Selected Candidate → Interview Agent → Human Selects Questions → Interview Feedback → Evaluation Agent → Final Recommendation → Email Agent → Human Approval → END
```

Conditional routing handles: resume parse failures → error node; high scores → interview agent; low scores → rejection draft; insufficient evidence → re-retrieval.

### Agents (each updates its own field in shared state)

| Agent | Input | Output | State Key |
|---|---|---|---|
| JD Agent | Raw JD text | Structured JD profile + rubric | `jd_profile` |
| Resume Agent | Resume text | Candidate profile JSON | `candidate_profiles` |
| Match Agent | JD profile + candidate profile + RAG evidence | Dimension scores + evidence | `match_results` |
| Ranking Agent | All match results | Ranked list + shortlist | `ranking_results` |
| Interview Agent | JD + candidate profile + match result + risks | Tailored interview questions | `interview_questions` |
| Evaluation Agent | Interview notes + feedback | Final evaluation + recommendation | `final_evaluations` |
| Email Agent | Candidate status + interview result | Email draft (invite/reject/follow-up) | `email_drafts` |

### Human-in-the-loop

These steps require human approval before proceeding (enforced via LangGraph interrupt nodes):
1. After candidate ranking (before shortlist finalization)
2. Before interview questions are finalized
3. Before final hiring recommendation
4. Before any HR email is sent (system only produces drafts)

### Scoring Rubric

Match Agent scores candidates across dimensions (total 100):
- Technical skills: 30, Project relevance: 20, Experience: 15, Education: 10, Domain relevance: 10, Communication: 5, Risk penalty: -10

### Planned Directory Structure

```
hireflow/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── api/                  # Route handlers (jobs, resumes, matching, interview, evaluation)
│   ├── agents/               # 7 agent implementations (jd_agent, resume_agent, match_agent, etc.)
│   ├── graph/                # LangGraph state.py, workflow.py, nodes.py
│   ├── schemas/              # Pydantic models for JD, resume, match, evaluation
│   ├── services/             # document_loader, embedding_service, vector_store, llm_service
│   ├── database/             # SQLAlchemy models, session, CRUD
│   └── utils/                # logger, config
├── evaluation/               # Eval scripts + datasets + reports
├── frontend/                 # Next.js pages, components, services
├── data/                     # Sample JDs, resumes, synthetic data
├── tests/
├── docker-compose.yml
└── requirements.txt
```

## Development Commands

本项目使用 conda 虚拟环境 `hireflowagents` (Python 3.11)。
每次开发前必须先激活此环境。

```bash
# 激活 conda 环境 (每次开发前必须执行)
conda activate hireflowagents

# 安装项目依赖
pip install -r requirements.txt

# 启动依赖服务 (PostgreSQL + Qdrant)
docker-compose up -d postgres qdrant

# Backend (Python/FastAPI)
uvicorn app.main:app --reload          # 启动 API 服务器 (开发模式)

# 测试
pytest                                  # 运行所有测试
pytest tests/test_match_agent.py -v     # 运行单个测试文件

# Frontend (Next.js)
cd frontend && npm install              # 安装依赖 (首次)
npm run dev                             # 启动 Next.js 开发服务器 → localhost:3000

# Docker 一键启动所有服务
docker-compose up -d                    # API + PostgreSQL + Qdrant
docker-compose down                     # 停止所有服务

# 环境变量
cp .env.example .env                    # 创建本地配置文件
# 编辑 .env 设置 LLM_MODE=local 或 LLM_MODE=cloud
```

## Evaluation Framework

The project includes a multi-dimensional evaluation system measuring:
- **Parsing quality**: Field accuracy, skill extraction precision/recall
- **Ranking quality**: Precision@K, NDCG@K, Spearman rank correlation
- **RAG evidence quality**: Context precision, faithfulness, evidence coverage
- **Workflow reliability**: Task success rate, invalid JSON rate, error recovery rate

Evaluation scripts live in `evaluation/` and produce JSON reports.

## Key Design Rules

- Agents must NEVER make final decisions autonomously — hiring is a high-stakes domain. Always route through human review nodes.
- Every match claim must be backed by retrievable evidence from the candidate's resume (RAG-based).
- Email Agent produces drafts only; sending requires explicit human approval.
- Use Pydantic schemas for all structured outputs to ensure parsing reliability.
- Do not use real private resumes without anonymization; prefer synthetic data for development and evaluation.

## Collaboration Rules

### 称呼

每次对话回复必须称呼用户为「番茄」。

### Git 安全网：每次代码改动前必须提交

在修改任何代码文件之前，必须先执行 `git add` 和 `git commit`，确保用户可以随时回退到改动前的状态。

**Why:** 用户是项目新手，可能对某些改动不满意或想对比前后差异。每次改动前打好 commit 快照，用户可以放心回退。

**执行流程:**
1. 改动前: `git add -A && git commit -m "<简要描述当前状态>"`
2. 然后进行代码改动
3. 如果用户要求回退: `git reset --hard HEAD~1` 或 `git checkout <commit> -- <file>`

### 代码注释：中文 + 逐行解释

所有代码必须写清晰的中文注释，默认用户是项目小白。

**要求:**
- 每个文件顶部用中文注释说明该文件的作用
- 每个函数/类用中文注释说明其职责、输入、输出
- 关键逻辑行用中文注释解释"为什么这样写"和"这行在做什么"
- 注释风格: 让一个刚学编程的人也能逐行读懂

**示例:**
```python
# 从环境变量中读取 API Key,如果没设置就用默认值
# os.getenv() 第一个参数是变量名,第二个参数是找不到时的默认值
api_key = os.getenv("OPENAI_API_KEY", "sk-default-key")
```

### Dev Logs 规则

当番茄要求写 dev logs 时，在 `logs/开发日志/` 目录下创建新的日志文件。

**命名格式:** `名字-YYYY-M-D.md`
- 名字: 2-8个字的简短描述 (如 `框架搭建`, `JD解析实现`, `RAG集成`)
- 日期: 创建当天的日期 (月份和日期不加前导零)
- 示例: `框架搭建-2026-5-31.md`, `JD解析Agent-2026-6-3.md`

**要求:**
- 内容使用中文
- 记录距离上次 dev log 以来的所有改动
- **必须包含当前系统的流程图**，使用代码块格式 (```)，不要用 Mermaid 或 box-drawing 字符
  - 用纯文本箭头 `-->` 和竖线 `|` 画流程
  - 示例格式:
    ```
    用户输入 --> JD Agent --> Resume Agent --> Match Agent --> Ranking Agent --> 结果展示
                     │            │               │
                     ▼            ▼               ▼
                  PostgreSQL   Qdrant(向量)    RAG证据检索
    ```
- 日志结构:
  1. 本次改动概述
  2. 系统流程图 (代码块纯文本格式)
  3. 详细改动列表 (文件 + 说明)
  4. 下一步计划

### Bug 解决沉淀规则

每次对话中只要解决了一个实际 Bug、稳定性问题、性能问题或真实联调问题，都必须同步更新:

`logs/面试准备-技术难点与Bug解决.md`

**目的:** 这个文件用于面试时讲述“项目中遇到过什么真实工程问题、如何定位、如何解决、带来了什么收益”。不要只记录代码改了什么，要记录可讲述的工程思路。

**触发条件:**
- 修复后端 API 500、LLM 解析失败、数据库重复数据等 bug
- 修复前端交互问题、loading、弹窗、状态不同步等 bug
- 做了明显性能优化，例如减少 LLM token、并发优化、缓存、粗筛等
- 解决真实联调问题，即使它不是严重 bug，也要记录

**写入位置:**
- 追加到合适分类下面；如果没有合适分类，就新增分类
- 编号必须延续已有编号，不能重复
- 不要重复已有案例；如果是同一个问题的新补充，就更新原条目

**固定格式:**

```markdown
### N. 问题标题

**现象:** 用户/系统表面上看到的问题是什么。要写具体，例如“Top 5 匹配返回 Failed to fetch”，不要只写“接口报错”。

**根因:** 经过排查后真正的技术原因是什么。要写到代码层、数据流层或模型调用层。

**解决:**
- 具体做了哪些修复
- 哪些文件/模块发生了关键变化
- 是否增加了兜底、测试、清洗、去重、限流、截断等工程防护

**面试说法:** 用第一人称写一段可以直接讲给面试官听的话，重点讲定位思路、技术取舍和结果。
```

**质量要求:**
- “现象”要贴近真实用户体验
- “根因”不能停留在猜测，要写清楚实际原因
- “解决”要体现工程防线，而不只是“改了一个 if”
- “面试说法”要自然，能展示番茄对系统的理解
- 如果本次修复影响测试数量或 README 状态，也要同步更新对应文档

### 测试规则

所有代码必须写测试。测试分为四层，每层独立跑通。

**Layer 1: Agent 单元测试 (mock LLM)**
- 每个 Agent 至少 3 个测试: 正常输出 / JSON回退 / 提示词构造
- Mock `call_llm` / `call_llm_structured`: `with patch("path.call_llm") as mock: mock.return_value = "预设"`
- 不调真实 LLM, 零外部依赖

**Layer 2: CRUD 集成测试 (SQLite 内存库)**
- `create_engine("sqlite:///:memory:")` + 事务回滚隔离
- 每个测试独立 session, 不相互影响

**Layer 3: API 集成测试 (FastAPI TestClient)**
- 文件临时库 (`sqlite:///tmp/hireflow_test.db`) 解决 SQLite 线程隔离
- `app.dependency_overrides[get_db]` 替换数据库依赖

**Layer 4: 端到端冒烟测试**
- 完整 7 步链路: JD→简历→匹配→面试→评价→邮件
- 验证路由可达 + 数据流转 + 字段存在

**运行:**
```bash
pytest tests/                    # 全量 (44 tests, 0 failures)
pytest tests/ -v                 # 详细
pytest tests/test_jd_agent.py    # 单个
```

**新增测试必须写入独立开发日志** (命名: `测试-功能名-YYYY-M-D.md`)，方便面试时讲解参数和指标。

<!-- CODEGRAPH_START -->
## CodeGraph

This project has a CodeGraph MCP server (`codegraph_*` tools) configured. CodeGraph is a tree-sitter-parsed knowledge graph of every symbol, edge, and file. Reads are sub-millisecond and return structural information grep cannot.

### When to prefer codegraph over native search

Use codegraph for **structural** questions — what calls what, what would break, where is X defined, what is X's signature. Use native grep/read only for **literal text** queries (string contents, comments, log messages) or after you already have a specific file open.

| Question | Tool |
|---|---|
| "Where is X defined?" / "Find symbol named X" | `codegraph_search` |
| "What calls function Y?" | `codegraph_callers` |
| "What does Y call?" | `codegraph_callees` |
| "What would break if I changed Z?" | `codegraph_impact` |
| "Show me Y's signature / source / docstring" | `codegraph_node` |
| "Give me focused context for a task/area" | `codegraph_context` |
| "See several related symbols' source at once" | `codegraph_explore` |
| "What files exist under path/" | `codegraph_files` |
| "Is the index healthy?" | `codegraph_status` |

### Rules of thumb

- **Answer directly — don't delegate exploration.** For "how does X work" / architecture / trace questions, answer with 2-3 codegraph calls: `codegraph_context` first, then ONE `codegraph_explore` for the source of the symbols it surfaces. Codegraph IS the pre-built index, so spawning a separate file-reading sub-task/agent — or running a grep + read loop — repeats work codegraph already did and costs more for the same answer.
- **Trust codegraph results.** They come from a full AST parse. Do NOT re-verify them with grep — that's slower, less accurate, and wastes context.
- **Don't grep first** when looking up a symbol by name. `codegraph_search` is faster and returns kind + location + signature in one call.
- **Don't chain `codegraph_search` + `codegraph_node`** when you just want context — `codegraph_context` is one call.
- **Don't loop `codegraph_node` over many symbols** — one `codegraph_explore` call returns several symbols' source grouped in a single capped call, while each separate node/Read call re-reads the whole context and costs far more.
- **Index lag**: the file watcher debounces ~500ms behind writes; don't re-query immediately after editing a file in the same turn.

### If `.codegraph/` doesn't exist

The MCP server returns "not initialized." Ask the user: *"I notice this project doesn't have CodeGraph initialized. Want me to run `codegraph init -i` to build the index?"*
<!-- CODEGRAPH_END -->
