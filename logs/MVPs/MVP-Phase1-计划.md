# HireFlow MVP Phase 1 计划

> 创建日期: 2026-05-31
> 状态: 规划中

## MVP 目标

构建最小完整闭环: 上传 JD → 上传简历 → 解析 → 匹配 → 排序 → 展示结果。

## MVP 技术栈清单

| 层级 | 选型 | 说明 |
|---|---|---|
| 数据库 | PostgreSQL | 生产级关系型数据库 |
| 向量数据库 | Qdrant | 高性能,支持过滤,适合 RAG 证据检索 |
| LLM (云端) | DeepSeek API | 性价比高,OpenAI 兼容接口 |
| LLM (本地) | LM Studio | 离线开发,免 API 费用 |
| Embedding (云端) | DeepSeek Embedding API | 与 LLM 同一供应商 |
| Embedding (本地) | LM Studio 本地模型 | 离线开发 |
| 结构化输出 | LangChain with_structured_output | 与 Pydantic 深度集成 |
| PDF 解析 | LangChain Document Loaders | 统一接口,多格式支持 |
| DOCX 解析 | python-docx | 成熟稳定 |
| 文本切分 | RecursiveCharacterTextSplitter | 智能边界切分 |
| LangGraph 持久化 | PostgresSaver | 支持中断恢复 |
| 配置管理 | Pydantic Settings | 类型安全,自动验证 |
| 前端 | Next.js + Tailwind CSS | 全栈框架,适合展示 |
| 部署 | Docker Compose | 单机多服务编排 |

## MVP 功能范围

### Phase 1.1: 核心 Pipeline (本次)
- [x] 项目文件结构
- [ ] 技术栈配置落地
- [ ] JD 上传与解析
- [ ] 简历上传与解析
- [ ] RAG 证据检索
- [ ] 候选人匹配评分
- [ ] 候选人排序
- [ ] 结果展示 (CLI 或 API)

### Phase 1.2: 完善与存储 (后续)
- [ ] Pydantic Schema 完善
- [ ] PostgreSQL 存储所有结果
- [ ] Qdrant 向量检索集成
- [ ] 错误处理完善

### Phase 1.3: RAG 证据 (后续)
- [ ] 简历 Chunking + Embedding
- [ ] Qdrant 检索 + 证据附加
- [ ] 评分可解释性

### Phase 1.4: 工作流完善 (后续)
- [ ] 完整 LangGraph 多 Agent 工作流
- [ ] Conditional Routing
- [ ] Human-in-the-loop

### Phase 1.5: 评估框架 (后续)
- [ ] 简历解析评估
- [ ] 排序质量评估
- [ ] RAG 证据评估
- [ ] 工作流稳定性评估

## MVP 数据规模

- 5 个岗位描述
- 30 份简历 (synthetic + 公开数据)
- 每个 JD 5-10 个候选人

## MVP 交付物

1. 可运行的 API 服务 (FastAPI + uvicorn)
2. 完整的 JD 解析 → 排序流程
3. Docker Compose 一键启动 (API + PostgreSQL + Qdrant)
4. 评估报告 (JSON 格式)
