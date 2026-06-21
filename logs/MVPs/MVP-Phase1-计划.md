# HireFlow MVP Phase 1 计划

> 最后更新: 2026-06-14
> 状态: Phase 1.1 完成, Phase 1.2 部分完成

## MVP 目标

构建完整招聘筛选系统: 上传 JD → 上传简历 → 解析 → 粗筛 → 精排 → 排序 → 展示。

## 技术栈 (已落地)

| 层级 | 选型 |
|---|---|
| 数据库 | PostgreSQL 16 |
| 向量数据库 | Qdrant |
| LLM (本地) | LM Studio + hermes-3-llama-3.1-8b |
| LLM (云端) | DeepSeek API + deepseek-v4-pro |
| Embedding (本地) | text-embedding-qwen3-embedding-4b (2560维) |
| 结构化输出 | LangChain with_structured_output (本地json_schema, 云端function_calling) |
| 配置 | Pydantic Settings |
| 前端 | Next.js + TypeScript + Tailwind CSS |
| 部署 | Docker Compose |

## 已完成功能

### 后端
- [x] 7 个 ORM 表 (jobs/candidates/resume_chunks/match_results/interview_questions/interview_evaluations/email_drafts)
- [x] 完整 CRUD + 删除 (+ 级联删除)
- [x] JD Agent: 结构化解析 + Rubric 生成
- [x] Resume Agent: 简历解析 → CandidateProfile (嵌套对象 + 中文输出)
- [x] Match Agent: 7 维度评分 + 强制中文后处理翻译
- [x] Ranking Agent: 排序 + LLM 解释
- [x] 两阶段匹配: pre_screening (关键词粗筛) + LLM 精排
- [x] RAG: document_loader → chunking → embedding → Qdrant
- [x] 11 个 API 端点 (含文件上传/删除/limit)
- [x] CLI Demo: python -m app.cli demo
- [x] 评估脚本: run_eval.py + Jupyter Notebook

### 前端
- [x] Dashboard: 统计卡片 + 流程提示
- [x] 岗位管理: 创建/解析/查看/删除
- [x] 简历管理: 文本粘贴 + PDF/DOCX 拖拽上传 → 自动解析
- [x] 匹配排名: 选岗位+limit → 两阶段匹配 → 排名表 → 详细评分
- [x] 匿名简历自动命名 (申请人A/B/C...)
- [x] 匹配进度计时器
- [x] 姓名映射 (ID → 姓名)

### Interview/Evaluation/Email Agent (Phase 1.2)
- [x] Interview Agent: 4 类面试问题生成
- [x] Evaluation Agent: 结构化面试评价 (requires_human_review=true)
- [x] Email Agent: 4 类邮件草稿 (status=draft, requires_human_approval=true)
- [x] 7 个新 API 端点
- [x] 7 个 CRUD 函数

### 测试体系
- [x] 44 个测试 (0 failures): 7个Agent + CRUD + API + 端到端冒烟
- [x] 4 层测试架构: mock LLM / SQLite CRUD / FastAPI TestClient / E2E

### 评估体系
- [x] Jupyter Notebook: 8 Cell (含 3 个新 Agent 测试)
- [x] run_eval.py: Precision@K / NDCG / Spearman ρ
- [x] 历史对比: 最近5次趋势

## 待完成

### Phase 1.3: 质量提升
- [ ] Ground Truth 人工标注
- [ ] 前端面试/评价/邮件页面
- [ ] Claude API 集成
- [ ] 匹配缓存
- [ ] 结果导出 (PDF/Excel)
- [ ] CI/CD 自动评估

## 已知限制
- 本地 hermes-3 输出中文不稳定 (已加后处理翻译)
- 大候选池 (>100人) 时匹配耗时较长 (已加两阶段+并行缓解)
- 无匹配缓存
- Workflow HITL 路径未实测
