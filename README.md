# HireFlow

基于 LangGraph 的多 Agent 招聘筛选与面试辅助系统。系统外层采用可控的
确定性 Workflow，在证据检索环节嵌入受控 ReAct Agent，通过原生 Tool Calling
动态查询候选人简历，并在自动恢复失败时进入 Human-in-the-loop。

## 项目简介

HireFlow 模拟完整招聘流程：JD 分析 → 简历解析 → 粗筛 → LLM 精排 → 面试问题 → 面试评价 → 邮件草稿。

**核心亮点:**
- 8 个专业 Agent (JD/Resume/Evidence/Match/Ranking/Interview/Evaluation/Email)
- Bounded ReAct Evidence Agent: `reason → tools → observation → reason`，最多 3 轮
- 原生 Tool Calling: Qdrant 证据搜索 + 证据覆盖率检查，全轨迹可审计
- 分层容错: 临时错误指数退避、非法参数由 Agent 修正、安全错误立即阻断
- Agent 人工兜底: 重试 / 带警告继续 / 跳过失败候选人 / 终止本轮
- 两阶段排序: 关键词粗筛 + LLM 精排 (ThreadPool 并行)
- RAG 证据检索 (简历向量化 + Qdrant 语义搜索)
- Human-in-the-loop 审核 (interrupt/resume)
- LLM 本地/云端双模式 (一键切换)
- PDF/DOCX 文件上传 + 自动解析 + 自动命名
- 前端产品化体验: 毛玻璃工作台、岗位/候选人内联改名、Portal 详情弹窗、局部 loading、连续解析
- LLM 稳定性兜底: 简历语义错位修复、匹配输出截断兜底评分
- 76 个测试 (0 failures)
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
pytest tests/                               # 76 tests
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

HireFlow 没有让一个 Supervisor Agent 自由控制整个招聘过程。招聘属于高风险
场景，因此主流程仍由 LangGraph 的固定节点和条件边控制；只有需要动态查询的
证据检索阶段使用 ReAct。

```text
JD Agent --> Resume Agent --> Resume Validation
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
                    |                              |
                    v                    重试/继续/跳过/终止
                Ranking Agent                       |
                    |-------------------------------|
                    v
                Human Review --> END
```

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
| `POST` | `/jobs/{id}/parse` | JD Agent 解析 |
| `GET` | `/jobs/{id}` | 岗位详情 |
| `PATCH` | `/jobs/{id}` | 人工修改岗位名称并同步结构化 JD |
| `DELETE` | `/jobs/{id}` | 删除岗位 |
| `POST` | `/resumes/upload` | 上传简历文本 |
| `POST` | `/resumes/upload-file` | 上传 PDF/DOCX/TXT |
| `POST` | `/resumes/{id}/parse` | Resume Agent 解析 (自动 RAG 索引) |
| `GET` | `/resumes/{id}` | 候选人详情 |
| `DELETE` | `/resumes/{id}` | 删除候选人 |

### 匹配与排名
| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/jobs/{id}/match?limit=N&agent_failure_action=ask_user` | ReAct 证据检索 + 粗筛精排 |
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
| 测试 | pytest (76 tests), SQLite 内存库, FastAPI TestClient |
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
│   ├── services/             # 6 个服务 (llm/embedding/vector/document/rag/pre_screening)
│   ├── database/             # ORM + CRUD (7 表)
│   └── utils/                # config + logger
├── frontend/                 # Next.js (4 页面)
├── evaluation/               # Notebook + 评估脚本 + reports
├── tests/                    # 76 tests (Agent/Tool重试/安全/RAG索引/CRUD/API/E2E)
├── data/                     # 测试数据
├── logs/                     # 项目文档 + 开发日志
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 安全与合规

- Agent 只生成建议/草稿，不做最终决定
- Evidence Agent 仅拥有当前候选人的只读检索工具，跨候选人调用立即阻断
- 年龄、性别、民族、婚姻、宗教等受保护属性禁止进入检索与评分
- `requires_human_review` / `requires_human_approval` = true
- 邮件 `status="draft"`，审核只改状态，不发送
- 不编造时间/地点/薪资/录用承诺
- API Key 从 `.env` 读取，不硬编码

## 稳定性设计

- Resume Agent: 姓名、邮箱、电话、教育、项目、技能优先从原文规则解析，LLM 输出作为补充，避免章节标题或乱码进入画像。
- Match Agent: prompt 自动截断，输出强制简洁；单个候选人 LLM 精排失败时返回规则兜底评分，不让 Top N 匹配整体失败。
- Evidence Agent: 最大 3 轮、6 次 Tool Call；候选人 ID 由可信运行时注入，常见本地模型参数别名先规范化；临时错误指数退避，不可兼容参数允许模型修正两次，重试耗尽后进入人工选择。
- RAG 索引健康检查: 匹配前检查每位候选人的 Qdrant 向量；缺失时从 PostgreSQL 简历原文自动重建，重建失败明确提示服务配置，不再误报“证据不足”。
- Qdrant 写入: Embedding 由 OpenAI 兼容接口生成后直接使用 QdrantClient upsert，不构造新版已禁止的 `embedding=None` LangChain 包装对象。
- Agent 审计: 保存 Tool Call、Observation 摘要、尝试次数、耗时、覆盖率和停止原因，不记录隐藏 CoT。
- 前端交互: 简历解析使用单卡片 loading + 后台同步，连续解析多个候选人时页面不会白屏。
- 人工命名: 岗位和候选人都支持卡片内联改名，并同步结构化画像；重新解析不会覆盖人工岗位名。
- 详情弹层: Agent 轨迹点击后在大弹窗展示；详细评分使用 React Portal 脱离页面动画定位上下文，打开时始终从弹窗顶部开始并只滚动弹窗内容。

## 常用命令

```bash
conda activate hireflowagents
docker compose up -d postgres qdrant
uvicorn app.main:app --reload
cd frontend && npm run dev
python -m app.cli demo
pytest tests/
```
