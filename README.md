# HireFlow

基于 LangGraph 的多 Agent 招聘筛选与面试辅助系统。系统外层采用可控的
确定性 Workflow，在证据检索环节嵌入受控 ReAct Agent，通过原生 Tool Calling
动态查询候选人简历，并在证据故障与最终排名两个节点进入 Human-in-the-loop。
当前前端的匹配执行只有 `/workflow/run` 一个入口，工作流状态通过 PostgreSQL
checkpoint 持久化，可跨请求中断和恢复。

## 项目简介

HireFlow 模拟完整招聘流程：JD 分析 → 简历解析 → LangGraph 粗筛/证据检索/精排 → 人工确认名单 → 面试问题 → 面试评价 → 邮件草稿。

**核心亮点:**
- 8 个专业 Agent (JD/Resume/Evidence/Match/Ranking/Interview/Evaluation/Email)
- Bounded ReAct Evidence Agent: `reason → tools → observation → reason`，最多 3 轮
- 原生 Tool Calling: Qdrant 证据搜索 + 证据覆盖率检查，全轨迹可审计
- 分层容错: 临时错误指数退避、非法参数由 Agent 修正、安全错误立即阻断
- Agent 人工兜底: 重试 / 带警告继续 / 跳过失败候选人 / 终止本轮
- 两阶段排序: 关键词召回 `max(3N, 15)` 人，整池完成证据检索与 LLM 评分后再返回 Top N
- RAG 证据检索 (简历向量化 + Qdrant 语义搜索)
- LangGraph 单一匹配入口: `/workflow/run`，不保留旧的直连 Agent 编排路由
- 双层 Human-in-the-loop: `interrupt()` + `Command(resume=...)`
- 唯一 `thread_id` + `AsyncPostgresSaver`，页面刷新后可恢复 checkpoint
- LLM 本地/云端双模式 (一键切换)
- PDF/DOCX 文件上传 + 自动解析 + 自动命名
- 前端产品化体验: 毛玻璃工作台、岗位/候选人内联改名、Portal 详情弹窗、局部 loading、连续解析
- LLM 稳定性兜底: 简历语义错位修复、匹配输出截断兜底评分
- 82 个测试 (0 failures)，覆盖两阶段精排、interrupt/resume、reject 循环和旧路由删除
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
pytest tests/                               # 82 tests
pytest tests/ -v                            # 详细
```

## 系统 Agent

| Agent | 职责 | 输出 |
|---|---|---|
| JD Agent | 解析岗位描述 | 结构化 JD + 评分 Rubric |
| Resume Agent | 解析简历 | 候选人画像 (教育/技能/项目/经历) |
| Evidence Agent | 受控 ReAct + Tool Calling | 简历原文证据 + 覆盖率 + 工具审计轨迹 |
| Match Agent | 匹配评分 | 7 维度分数 + 证据 |
| Ranking Agent | 排序 | 排名表 + Shortlist + 解释 |
| Interview Agent | 面试问题 | 4 类定制化问题 (技术/项目/行为/风险) |
| Evaluation Agent | 面试评价 | 技术/沟通/问题解决 + 推荐建议 |
| Email Agent | 邮件草稿 | 面试邀请/拒信/跟进/下一轮 |

## Workflow 与 ReAct 的组合架构

HireFlow 没有让一个 Supervisor Agent 自由控制整个招聘过程。岗位/简历上传解析、
面试、评价和邮件是独立资源 API；核心匹配筛选则统一进入 LangGraph。招聘属于
高风险场景，因此图中的主流程由固定节点和条件边控制，只有需要动态查询的证据
检索阶段使用 ReAct。

```text
/workflow/run
      |
      v
读取 PostgreSQL 已解析 JD/候选人 --> 关键词召回池 max(3N, 15) --> 构建 initial state
                                                                   |
                                                                   v
JD Agent(复用画像) --> Resume Agent(复用画像) --> Resume Validation
                                  |
                                  v
                      Evidence ReAct Agent
                                  |
                 reason --> tool calling --> observation
                    ^                              |
                    |---------- 最多3轮 -----------|
                                  |
                    |-------------|----------------|
                    |成功         |证据不足         |技术失败
                    v             v                v
                Match Agent   标记人工复核    Evidence Intervention
             (召回池全部评分)                         |
                    |                              |
                    v                    重试/继续/跳过/终止
                Ranking Agent                       |
              (排序后截取 Top N)                    |
                    |-------------------------------|
                    v
                Human Review -- interrupt() --> 人工勾选名单
                                                |
                                      Command(resume=...)
                                                |
                                                v
                                               END
```

每次启动都会生成唯一 `thread_id`。`AsyncPostgresSaver` 在节点执行后保存 checkpoint；
前端保存 thread ID，可通过状态接口恢复证据审核或排名审核现场。审核完成后，页面只
展示最终入选候选人，未入选者不会解锁面试操作。

两阶段排序中的 `N` 是 HR 选择的最终返回人数。例如选择 Top 5 时，关键词规则先从
全部已解析候选人中召回 `max(5 × 3, 15) = 15` 人；这 15 人全部经过 Evidence ReAct
证据检索和 Match Agent 七维 LLM 评分，Ranking Agent 再按总分稳定排序并截取前 5。
因此关键词只决定“谁进入成本更高的精排池”，不会提前决定最终 Top 5。若数据库中
不足 15 人，则召回全部候选人；选择“全部”时不执行最终截断。

### Tool Calling 与重试边界

| 情况 | 处理方式 |
|---|---|
| Timeout、ConnectionError、HTTP 429/5xx | 原参数指数退避，总尝试 3 次 |
| candidate_id 省略、常见工具/字段别名、数字字符串 | 运行时注入或规范化后安全执行 |
| top_k 越界、重复 Tool Call 等不可安全兼容参数 | 作为 ToolMessage 返回，允许 Agent 改参数 |
| 工具正常但没有结果 | 标记 `insufficient_evidence`，不是系统错误 |
| 跨候选人检索、受保护属性查询 | 立即阻断，不自动重试 |
| 自动重试耗尽、模型连续非法调用 | 暂停并交给用户选择 |

完整 Tool Call 轨迹包含工具名、参数、轮数、尝试次数、耗时、Observation、
停止原因和证据覆盖率，但不会保存模型隐藏思维链。

## API 端点

### 岗位与简历
| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/jobs/upload` | 上传岗位描述 |
| `POST` | `/jobs/{job_id}/parse` | JD Agent 解析 |
| `GET` | `/jobs/` | 岗位列表 |
| `GET` | `/jobs/{job_id}` | 岗位详情 |
| `PATCH` | `/jobs/{job_id}` | 人工修改岗位名称并同步结构化 JD |
| `DELETE` | `/jobs/{job_id}` | 删除岗位 |
| `POST` | `/resumes/upload` | 上传简历文本 |
| `POST` | `/resumes/upload-file` | 上传 PDF/DOCX/TXT |
| `POST` | `/resumes/{candidate_id}/parse` | Resume Agent 解析 (自动 RAG 索引) |
| `GET` | `/resumes/` | 候选人列表 |
| `GET` | `/resumes/{candidate_id}` | 候选人详情 |
| `PATCH` | `/resumes/{candidate_id}` | 人工修改姓名并同步结构化画像 |
| `DELETE` | `/resumes/{candidate_id}` | 删除候选人 |

### 匹配结果（只读）
| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/jobs/{job_id}/ranking?limit=N` | 排名结果 |
| `GET` | `/jobs/{job_id}/candidates/{candidate_id}/detail` | 详细评分 |

旧的 `POST /jobs/{job_id}/match` 已删除，避免普通 API 与 LangGraph 维护两套匹配编排。

### 面试、评价、邮件
| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/jobs/{job_id}/candidates/{candidate_id}/questions` | 生成面试问题 |
| `GET` | `/jobs/{job_id}/candidates/{candidate_id}/questions` | 获取问题列表 |
| `POST` | `/jobs/{job_id}/candidates/{candidate_id}/evaluate` | 提交面试评价 |
| `GET` | `/jobs/{job_id}/candidates/{candidate_id}/evaluation` | 获取评价 |
| `POST` | `/jobs/{job_id}/candidates/{candidate_id}/email-draft` | 生成邮件草稿 |
| `GET` | `/jobs/{job_id}/candidates/{candidate_id}/email-draft` | 获取草稿列表 |
| `POST` | `/email-drafts/{email_id}/approve` | 批准草稿 (不发送) |

### 工作流
| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/workflow/run` | 传入 `job_id`/`limit`，启动唯一匹配工作流 |
| `POST` | `/workflow/{thread_id}/resume` | 提交人工选择并从 interrupt 恢复 |
| `GET` | `/workflow/{thread_id}/state` | 从 PostgreSQL checkpoint 查询状态 |

## 技术栈

| 层级 | 技术 |
|---|---|
| 后端 | Python 3.11, FastAPI, LangGraph, LangChain |
| LLM 本地 | LM Studio + hermes-3-llama-3.1-8b |
| LLM 云端 | DeepSeek API + deepseek-v4-flash |
| Embedding | text-embedding-qwen3-embedding-4b (2560维) |
| 数据库 | PostgreSQL 16 (业务数据 + LangGraph checkpoint) |
| 向量库 | Qdrant |
| 前端 | Next.js 14 + TypeScript + Tailwind CSS |
| 测试 | pytest (82 tests), SQLite/InMemorySaver, FastAPI TestClient |
| 配置 | Pydantic Settings + .env |
| 部署 | Docker Compose |

## 项目结构

```
HireFlowAgents/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── cli.py               # CLI Demo
│   ├── api/                  # 6 个路由 (jobs/resumes/matching/interview/evaluation/workflow)
│   ├── agents/               # 8 个 Agent，含受控 ReAct Evidence Agent
│   ├── graph/                # LangGraph (state/nodes/workflow + HITL)
│   ├── schemas/              # Pydantic 模型
│   ├── services/             # 7 个服务 (含 matching 前置检查与索引自愈)
│   ├── database/             # ORM + CRUD (7 表)
│   └── utils/                # config + logger
├── frontend/                 # Next.js (4 页面)
├── evaluation/               # Notebook + 评估脚本 + reports
├── tests/                    # 82 tests (Agent/HITL/两阶段精排/Tool重试/安全/RAG/CRUD/API/E2E)
├── data/                     # 测试数据
├── logs/                     # 项目文档 + 开发日志
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 安全与合规

- Agent 只生成建议/草稿，不做最终决定
- 排名必须经过 LangGraph interrupt 人工确认，确认前不会解锁面试操作
- Evidence Agent 仅拥有当前候选人的只读检索工具，跨候选人调用立即阻断
- 年龄、性别、民族、婚姻、宗教等受保护属性禁止进入检索与评分
- `requires_human_review` / `requires_human_approval` = true
- 邮件 `status="draft"`，审核只改状态，不发送
- 不编造时间/地点/薪资/录用承诺
- API Key 从 `.env` 读取，不硬编码

## 稳定性设计

- Resume Agent: 姓名、邮箱、电话、教育、项目、技能优先从原文规则解析，LLM 输出作为补充，避免章节标题或乱码进入画像。
- Match Agent: 对关键词召回池中的全部候选人执行七维 LLM 评分，最多 5 个线程并发；prompt 自动截断，输出强制简洁；单个候选人失败时返回规则兜底评分，不让整批精排失败。
- Evidence Agent: 最大 3 轮、6 次 Tool Call；候选人 ID 由可信运行时注入，常见本地模型参数别名先规范化；临时错误指数退避，不可兼容参数允许模型修正两次，重试耗尽后进入人工选择。
- RAG 索引健康检查: 匹配前检查每位候选人的 Qdrant 向量；缺失时从 PostgreSQL 简历原文自动重建，重建失败明确提示服务配置，不再误报“证据不足”。
- Qdrant 写入: Embedding 由 OpenAI 兼容接口生成后直接使用 QdrantClient upsert，不构造新版已禁止的 `embedding=None` LangChain 包装对象。
- Agent 审计: 保存 Tool Call、Observation 摘要、尝试次数、耗时、覆盖率和停止原因，不记录隐藏 CoT。
- 工作流持久化: 每次运行生成唯一 thread_id，使用 AsyncPostgresSaver 保存 checkpoint，并通过 Command(resume=...) 恢复。
- 单一编排入口: 匹配执行只允许 `/workflow/run`；OpenAPI 测试断言旧 `/jobs/{job_id}/match` 不存在。
- 前端交互: 简历解析使用单卡片 loading + 后台同步，连续解析多个候选人时页面不会白屏。
- 人工命名: 岗位和候选人都支持卡片内联改名，并同步结构化画像；重新解析不会覆盖人工岗位名。
- 详情弹层: Agent 轨迹点击后在大弹窗展示；详细评分使用 React Portal 脱离页面动画定位上下文，打开时始终从弹窗顶部开始并只滚动弹窗内容。
- 人审结果: 审核期间展示完整排名供 HR 比较；确认后只保留最终面试名单，其他候选人隐藏且无法进入面试流程。

## 常用命令

```bash
conda activate hireflowagents
docker compose up -d postgres qdrant
uvicorn app.main:app --reload
cd frontend && npm run dev
python -m app.cli demo
pytest tests/
```
