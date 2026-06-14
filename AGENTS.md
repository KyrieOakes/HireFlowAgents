# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

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
