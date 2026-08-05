# HireFlow：基于 LangGraph 的多 Agent 招聘筛选与面试辅助系统

## 1. 项目概述

HireFlow 是一个基于 LangGraph 的多 Agent 招聘筛选系统。  
这个项目的目标是从企业招聘方或 HR 的视角，模拟一个较完整的招聘流程。

它不是简单地上传一份简历，然后让大模型给一个分数，而是构建一套完整的工作流，包括岗位描述理解、简历解析、候选人匹配、候选人排序、面试题生成、面试评价和 HR 邮件草稿生成。

这个项目主要面向校招简历展示，重点体现以下能力：

- LLM 应用开发
- Multi-Agent 工作流设计
- LangGraph 状态图编排
- RAG 证据检索
- 结构化输出
- 评估体系设计
- Human-in-the-loop 人工审核机制
- 后端工程化能力

### 当前实现状态（2026-6-21 更新）

项目已经从早期规划稿推进到可演示的完整 MVP：

- 7 个 Agent 已实现：JD、Resume、Match、Ranking、Interview、Evaluation、Email
- FastAPI 已提供岗位、简历、匹配、面试、评价、邮件、workflow 等核心接口
- 前端已实现 Dashboard、岗位管理、简历管理、匹配与面试工作台
- RAG 已接入简历解析和匹配流程：解析后自动索引到 Qdrant，匹配时按候选人检索证据
- LangGraph HITL 已具备 interrupt/resume 能力，支持人工审核后继续执行
- Match Agent 已加入粗筛、ThreadPool 并行、prompt 截断和 LLM 失败兜底评分
- Resume Agent 已加入原文规则解析和乱码/语义错位防线
- 前端已完成毛玻璃视觉、详情弹层、局部 loading、连续解析等产品化体验优化
- 测试体系已覆盖 Agent、CRUD、API、端到端冒烟测试，当前 `pytest -q` 为 51 个测试通过

## 2. 项目名称

HireFlow

完整项目名：

HireFlow：基于 LangGraph 的多 Agent 招聘筛选与面试辅助系统

英文名：

HireFlow: Multi-Agent Recruitment Screening and Interview Assistant

## 3. 项目背景

招聘流程不是一个单步骤任务。在真实的招聘场景中，HR 或 Hiring Manager 通常需要完成以下工作：

- 理解岗位描述
- 提取岗位核心要求
- 阅读和比较大量简历
- 判断候选人与岗位的匹配程度
- 对候选人进行排序
- 为候选人生成针对性的面试问题
- 根据面试表现进行评价
- 发送面试邀请、拒信或后续沟通邮件

这个过程重复性强、耗时长，而且不同 HR 或面试官之间可能存在判断标准不一致的问题。

大语言模型可以帮助完成文档理解和推理任务，但是如果只用一个大 Prompt 来完成所有工作，系统会很难维护，也很难评估。因此，本项目使用 LangGraph 搭建一个受控的多 Agent 工作流。每个 Agent 负责一个明确的任务，整个招聘流程由 LangGraph 的 StateGraph 进行管理。

## 4. 项目目标

本项目的主要目标包括：

1. 使用 LangGraph 构建完整的招聘筛选工作流
2. 将岗位描述和简历解析为结构化数据
3. 使用基于评分 Rubric 的方式对候选人进行匹配评分
4. 使用 RAG 为候选人评价提供简历证据
5. 生成可解释的候选人排序结果
6. 根据候选人简历和岗位要求生成定制化面试问题
7. 支持面试后的候选人评价和最终推荐
8. 生成 HR 邮件草稿，并加入人工审核机制
9. 构建系统评估框架，衡量系统输出质量
10. 打造一个适合放入校招简历并能在面试中讲清楚的项目

## 5. 核心使用场景

系统主要支持以下几个使用场景。

### 5.1 岗位描述分析

用户上传或粘贴岗位描述。  
系统自动提取：

- 岗位名称
- 必备技能
- 加分技能
- 岗位职责
- 学历要求
- 经验要求
- 技术要求
- 软技能要求
- 候选人评价 Rubric

### 5.2 简历解析

用户上传多份候选人简历。  
系统自动提取：

- 候选人姓名
- 教育背景
- 工作经历
- 实习经历
- 技术技能
- 项目经历
- 证书
- 经验年限
- 候选人优势
- 候选人风险点
- 缺失信息

### 5.3 候选人匹配

系统将每个候选人与岗位描述进行对比。  
输出内容包括：

- 总匹配分数
- 各维度分数
- 候选人优势
- 候选人弱点
- 风险点
- 来自简历的证据
- 是否推荐进入面试

### 5.4 候选人排序

系统根据匹配结果对所有候选人进行排序。

输出内容包括：

- 候选人排名
- 候选人总分
- 推荐等级
- 排名解释
- Shortlist 推荐名单

### 5.5 面试题生成

对于被选中的候选人，系统可以生成定制化面试问题。

问题类型包括：

- 技术问题
- 项目深挖问题
- 行为面试问题
- 风险验证问题
- 岗位相关问题

### 5.6 面试评价

面试结束后，用户可以输入面试记录或候选人回答。  
系统自动评价：

- 回答质量
- 技术深度
- 沟通表达
- 问题解决能力
- 之前的风险点是否被解决
- 最终推荐结果

### 5.7 HR 邮件草稿生成

系统可以生成以下邮件草稿：

- 面试邀请邮件
- 拒信
- 后续跟进邮件
- 下一轮面试通知邮件

注意：系统只生成邮件草稿，不自动发送邮件。  
发送前必须由人工审核。

## 6. 为什么使用 LangGraph

LangGraph 是本项目的核心框架。

选择 LangGraph 的原因是：这个项目不是一个简单的聊天机器人，而是一个多步骤、可控、有状态的招聘工作流。它需要在多个 Agent 之间传递状态，并根据不同条件进行流程跳转。

LangGraph 适合本项目，因为它支持：

- StateGraph 工作流设计
- Agent 之间共享状态
- 条件边 Conditional Edges
- 工具调用 Tool Calling
- 多 Agent 编排
- Human-in-the-loop 人工介入
- 可调试的执行路径
- 比完全自由的 Agent 更强的流程控制能力

在本项目中，LangGraph 用来管理完整招聘流程。每一个节点代表一个 Agent 或处理步骤，全局 state 用来保存各个步骤生成的信息。

## 7. 系统整体架构

系统可以分为六层。

### 7.1 文档输入与预处理层

这一层负责读取和预处理文档。

输入包括：

- 岗位描述 PDF
- 岗位描述文本
- 简历 PDF
- 简历 DOCX
- 面试记录 TXT

主要任务：

- 加载文档
- 提取文本
- 清洗文本
- 将长文档切分为 chunks
- 保存 metadata
- 为 embedding 和检索做准备

可选工具：

- PyMuPDF
- pdfplumber
- python-docx
- LangChain document loaders

### 7.2 信息抽取层

这一层负责将非结构化文本转换为结构化 JSON 数据。

主要包括：

- JD 信息抽取
- 简历信息抽取
- 候选人画像构建
- 技能抽取
- 经验抽取
- 项目经历抽取

结构化输出建议使用 Pydantic schema 控制。

### 7.3 检索层

这一层提供基于 RAG 的证据检索能力。

系统会将简历 chunks 存入向量数据库。
当 Match Agent 需要证据时，可以按 `candidate_id` 从 Qdrant 中检索相关简历片段，用来支撑评分。

主要任务：

- 对简历进行 chunking
- 生成 embeddings
- 存储向量
- 检索相关证据
- 根据 candidate_id 进行过滤
- 返回带 metadata 的证据

当前实现：

- 向量数据库使用 Qdrant
- 解析简历后自动执行 chunking、embedding、upsert
- 数据库保存 chunk 与 Qdrant point_id 的映射，保证检索证据可追溯

### 7.4 多 Agent 工作流层

这是整个项目的核心层。

使用 LangGraph 将多个 Agent 连接成一个完整的招聘流程。

主要 Agent 包括：

- JD Agent
- Resume Agent
- Match Agent
- Ranking Agent
- Interview Agent
- Evaluation Agent
- Email Agent

### 7.5 API 层

后端为前端提供 API 接口。

推荐框架：

- FastAPI

主要 API 功能：

- 上传岗位描述
- 上传简历
- 解析岗位描述
- 解析简历
- 匹配候选人
- 获取候选人排名
- 生成面试问题
- 提交面试反馈
- 生成邮件草稿
- 获取评估报告

### 7.6 前端展示层

前端主要用于项目演示和面试展示。

推荐框架：

- React
- Next.js
- Tailwind CSS

主要页面：

- Dashboard 页面
- 岗位详情页
- 候选人排名页
- 候选人详情页
- 面试问题页
- 邮件草稿页
- 评估报告页

## 8. Agent 设计

## 8.1 JD Agent

### 职责

JD Agent 负责分析岗位描述，并提取结构化岗位需求。

### 输入

- 原始岗位描述文本

### 输出

- 结构化 JD profile

### 主要任务

- 提取岗位名称
- 提取必备技能
- 提取加分技能
- 提取岗位职责
- 提取学历要求
- 提取经验要求
- 生成候选人评分 Rubric

### 示例输出

```json
{
  "job_title": "Junior AI Engineer",
  "required_skills": ["Python", "Machine Learning", "LLM"],
  "preferred_skills": ["LangChain", "RAG", "FastAPI"],
  "responsibilities": [
    "Build LLM applications",
    "Develop backend APIs",
    "Evaluate model outputs"
  ],
  "education_requirements": ["Computer Science or related field"],
  "experience_requirements": "0-2 years",
  "rubric": {
    "technical_skills": 30,
    "project_relevance": 20,
    "experience": 15,
    "education": 10,
    "domain_relevance": 10,
    "communication": 5,
    "risk_penalty": -10
  }
}
```

## 8.2 Resume Agent

### 职责

Resume Agent 负责解析简历，并构建结构化候选人画像。

### 输入

- 简历文本
- 简历 metadata

### 输出

- 候选人 profile JSON

### 主要任务

- 提取候选人基本信息
- 提取教育背景
- 提取技能
- 提取项目经历
- 提取实习或工作经历
- 识别候选人优势
- 识别候选人风险点
- 识别缺失信息

### 示例输出

```json
{
  "candidate_id": "C001",
  "name": "Candidate A",
  "education": [
    {
      "degree": "Master of Artificial Intelligence",
      "school": "University Example",
      "major": "AI"
    }
  ],
  "skills": ["Python", "FastAPI", "RAG", "LangGraph"],
  "projects": [
    {
      "name": "Local RAG System",
      "description": "Built a RAG system using FastAPI and Qdrant"
    }
  ],
  "strengths": [
    "Strong LLM application experience",
    "Relevant RAG project experience"
  ],
  "risks": [
    "Limited production deployment experience"
  ],
  "missing_info": [
    "No clear internship experience"
  ]
}
```

## 8.3 Match Agent

### 职责

Match Agent 负责比较 JD profile 和候选人 profile。

### 输入

- JD profile
- Candidate profile
- 从简历 chunks 中检索到的 evidence

### 输出

- 候选人匹配结果

### 主要任务

- 比较必备技能
- 比较加分技能
- 评估项目相关性
- 评估经验水平
- 评估教育背景
- 识别风险点
- 生成基于证据的评分

### 评分维度

| 维度 | 分数 |
|---|---:|
| 技术技能匹配 | 30 |
| 项目相关性 | 20 |
| 工作或实习经验 | 15 |
| 教育背景 | 10 |
| 领域相关性 | 10 |
| 沟通表达指标 | 5 |
| 风险扣分 | -10 |
| 总分 | 100 |

### 示例输出

```json
{
  "candidate_id": "C001",
  "total_score": 82,
  "dimension_scores": {
    "technical_skills": 27,
    "project_relevance": 18,
    "experience": 12,
    "education": 8,
    "domain_relevance": 9,
    "communication": 4,
    "risk_penalty": -6
  },
  "strengths": [
    "Strong Python and FastAPI experience",
    "Relevant RAG project experience"
  ],
  "risks": [
    "No clear production deployment experience"
  ],
  "evidence": [
    {
      "claim": "The candidate has RAG experience",
      "source": "resume_page_2",
      "text": "Built a local RAG system using Qdrant and FastAPI"
    }
  ],
  "recommendation": "Shortlist"
}
```

## 8.4 Ranking Agent

### 职责

Ranking Agent 负责根据匹配结果对所有候选人进行排序。

### 输入

- 所有候选人的 match results

### 输出

- 排序后的候选人列表

### 主要任务

- 根据分数排序候选人
- 按推荐等级分组
- 解释排序结果
- 生成 shortlist

### 推荐等级

- Strong match
- Medium match
- Weak match
- Not recommended

## 8.5 Interview Agent

### 职责

Interview Agent 负责为被选中的候选人生成定制化面试问题。

### 输入

- JD profile
- Candidate profile
- Match result
- Candidate risks
- Retrieved evidence

### 输出

- 面试问题

### 问题类型

- 技术问题
- 项目深挖问题
- 行为问题
- 风险验证问题

### 示例问题

```json
{
  "candidate_id": "C001",
  "questions": [
    {
      "type": "technical",
      "question": "Can you explain how your RAG system retrieves relevant documents and generates answers?",
      "purpose": "Test the candidate's understanding of RAG architecture"
    },
    {
      "type": "project_deep_dive",
      "question": "In your FastAPI and Qdrant project, how did you design the chunking and embedding process?",
      "purpose": "Verify the candidate's real project experience"
    },
    {
      "type": "risk_verification",
      "question": "Your resume does not clearly mention deployment experience. Have you deployed any backend or AI system before?",
      "purpose": "Check missing information"
    }
  ]
}
```

## 8.6 Evaluation Agent

### 职责

Evaluation Agent 负责在面试后对候选人进行评价。

### 输入

- 面试记录
- 面试官笔记
- Candidate profile
- Match result
- JD profile

### 输出

- 最终面试评价

### 主要任务

- 总结面试表现
- 评价技术深度
- 评价沟通能力
- 判断之前的风险点是否被解决
- 生成最终推荐结果

## 8.7 Email Agent

### 职责

Email Agent 负责生成 HR 邮件草稿。

### 输入

- Candidate profile
- Candidate status
- Interview result
- Email type

### 输出

- 邮件草稿

### 邮件类型

- 面试邀请
- 拒信
- 下一轮面试通知
- Follow-up 邮件

### 重要规则

Email Agent 只创建邮件草稿。  
邮件必须由人工用户审核并确认后，才能发送。

## 9. LangGraph 工作流设计

本项目使用 LangGraph StateGraph 控制完整流程。

### 9.1 面试前筛选工作流

```text
START
  ↓
JD Agent
  ↓
Resume Agent
  ↓
Resume Validation Node
  ↓
Evidence Retrieval Node
  ↓
Match Agent
  ↓
Ranking Agent
  ↓
Human Review Node
  ↓
END
```

### 9.2 面试辅助工作流

```text
START
  ↓
Selected Candidate
  ↓
Interview Agent
  ↓
Human Selects Questions
  ↓
Interview Feedback Input
  ↓
Evaluation Agent
  ↓
Final Recommendation
  ↓
Email Agent
  ↓
Human Approval
  ↓
END
```

### 9.3 条件路由设计

工作流中应该加入 conditional routing。

示例：

- 如果简历解析失败，进入错误处理节点
- 如果候选人分数较高，进入 Interview Agent
- 如果候选人分数较低，进入拒信草稿生成节点
- 如果需要人工审核，流程暂停等待人工确认
- 如果 evidence 不足，返回 retrieval node 重新检索

## 10. LangGraph State 设计

系统使用一个共享 state 对象。

示例：

```python
from typing_extensions import TypedDict
from typing import List, Dict, Any

class HiringState(TypedDict):
    job_id: str
    jd_text: str
    jd_profile: Dict[str, Any]

    resume_texts: Dict[str, str]
    candidate_profiles: List[Dict[str, Any]]

    resume_chunks: List[Dict[str, Any]]
    retrieved_evidence: Dict[str, List[Dict[str, Any]]]

    match_results: List[Dict[str, Any]]
    ranking_results: List[Dict[str, Any]]

    selected_candidate_ids: List[str]
    interview_questions: Dict[str, List[Dict[str, Any]]]

    interview_feedback: Dict[str, str]
    final_evaluations: Dict[str, Dict[str, Any]]

    email_drafts: Dict[str, Dict[str, str]]

    human_review_status: str
    errors: List[str]
```

每个 Agent 只更新自己负责的字段。

示例：

- JD Agent 更新 `jd_profile`
- Resume Agent 更新 `candidate_profiles`
- Retrieval Node 更新 `retrieved_evidence`
- Match Agent 更新 `match_results`
- Ranking Agent 更新 `ranking_results`
- Interview Agent 更新 `interview_questions`
- Evaluation Agent 更新 `final_evaluations`
- Email Agent 更新 `email_drafts`

## 11. Human-in-the-loop 设计

因为招聘属于高影响决策场景，所以系统不能完全自动做最终决定。

以下步骤必须加入人工审核：

1. 候选人排序之后
2. 面试问题最终确认前
3. 最终招聘推荐前
4. HR 邮件发送前

系统只提供建议，最终决定必须由人工用户完成。

## 12. 数据库设计

### 12.1 jobs 表

| 字段 | 说明 |
|---|---|
| job_id | 岗位唯一 ID |
| title | 岗位名称 |
| company | 公司名称 |
| jd_text | 原始岗位描述 |
| jd_profile_json | 结构化 JD 结果 |
| rubric_json | 评分 Rubric |
| created_at | 创建时间 |

### 12.2 candidates 表

| 字段 | 说明 |
|---|---|
| candidate_id | 候选人唯一 ID |
| name | 候选人姓名 |
| email | 候选人邮箱 |
| resume_filename | 简历文件名 |
| resume_text | 原始简历文本 |
| profile_json | 结构化候选人画像 |
| created_at | 创建时间 |

### 12.3 resume_chunks 表

| 字段 | 说明 |
|---|---|
| chunk_id | chunk 唯一 ID |
| candidate_id | 候选人 ID |
| text | 简历 chunk 文本 |
| qdrant_point_id | Qdrant 向量 ID |
| page_number | 来源页码 |
| source | 来源文件 |

### 12.4 match_results 表

| 字段 | 说明 |
|---|---|
| match_id | 匹配结果唯一 ID |
| job_id | 岗位 ID |
| candidate_id | 候选人 ID |
| total_score | 总分 |
| dimension_scores_json | 各维度分数 |
| evidence_json | 评分证据 |
| risk_json | 风险点 |
| strengths_json | 优势 |
| recommendation | 推荐等级 |
| summary | 匹配总结 |
| created_at | 创建时间 |

### 12.5 interview_questions 表

| 字段 | 说明 |
|---|---|
| question_id | 问题唯一 ID |
| job_id | 岗位 ID |
| candidate_id | 候选人 ID |
| question_type | 技术、行为、项目、风险 |
| question | 面试问题 |
| purpose | 提问目的 |

### 12.6 interview_evaluations 表

| 字段 | 说明 |
|---|---|
| evaluation_id | 评价唯一 ID |
| candidate_id | 候选人 ID |
| job_id | 岗位 ID |
| feedback_text | 面试反馈 |
| evaluation_json | 结构化评价 |
| final_recommendation | 最终推荐 |

### 12.7 email_drafts 表

| 字段 | 说明 |
|---|---|
| email_id | 邮件唯一 ID |
| candidate_id | 候选人 ID |
| job_id | 岗位 ID |
| email_type | 邀请、拒信、follow-up |
| subject | 邮件标题 |
| body | 邮件正文 |
| status | 草稿、已批准、已拒绝 |

## 13. API 设计

后端可以使用 FastAPI 搭建。

### 13.1 Job APIs

```text
POST /jobs/upload
POST /jobs/{job_id}/parse
GET /jobs/{job_id}
GET /jobs/
DELETE /jobs/{job_id}
```

### 13.2 Resume APIs

```text
POST /resumes/upload
POST /resumes/upload-file
POST /resumes/{candidate_id}/parse
GET /resumes/{candidate_id}
GET /resumes/
DELETE /resumes/{candidate_id}
```

### 13.3 Matching Result APIs

```text
GET /jobs/{job_id}/ranking?limit=N
GET /jobs/{job_id}/candidates/{candidate_id}/detail
```

匹配执行不再提供独立 Job 路由，统一通过 13.6 的 LangGraph Workflow API 启动。

### 13.4 Interview APIs

```text
POST /jobs/{job_id}/candidates/{candidate_id}/questions
GET /jobs/{job_id}/candidates/{candidate_id}/questions
POST /jobs/{job_id}/candidates/{candidate_id}/evaluate
GET /jobs/{job_id}/candidates/{candidate_id}/evaluation
```

### 13.5 Email APIs

```text
POST /jobs/{job_id}/candidates/{candidate_id}/email-draft
GET /jobs/{job_id}/candidates/{candidate_id}/email-draft
POST /email-drafts/{email_id}/approve
```

### 13.6 Workflow APIs

```text
POST /workflow/run
POST /workflow/{thread_id}/resume
GET /workflow/{thread_id}/state
```

## 14. 前端页面设计

前端用于项目演示和面试展示，当前采用 Next.js + Tailwind CSS，整体风格偏 HR/ATS 工作台。

### 14.1 Dashboard 页面

展示内容：

- 岗位数量
- 候选人数量
- 已解析简历数量
- shortlist 候选人数量
- 工作流运行状态

### 14.2 岗位管理页

展示内容：

- JD 上传与解析
- 岗位列表
- 原始 JD
- 必备技能
- 加分技能
- 岗位职责
- 评分 Rubric
- 详情弹层

### 14.3 简历管理页

展示内容：

- 粘贴简历文本
- PDF/DOCX/TXT/MD 文件上传
- 候选人列表
- 单候选人解析状态
- 结构化候选人画像
- 原始简历文本
- 详情弹层

### 14.4 匹配与面试页

展示内容：

- 选择岗位
- 选择 Top N 匹配人数
- 候选人列表
- 总分
- 各维度分数
- 推荐等级
- 优势
- 风险点
- 简历证据
- 匹配解释
- 面试问题生成
- 面试反馈输入
- 结构化评价结果
- 邮件类型
- 邮件草稿生成与审批

### 14.5 产品化交互优化

当前前端已加入以下体验优化：

- 毛玻璃面板和统一卡片样式
- 页面进入和按钮 hover 动效
- 详情弹层高层级显示，避免被顶部导航遮挡
- 弹层自身滚动，长内容详情可完整查看
- 简历解析使用单卡片 loading，连续解析多个候选人时页面不白屏

## 15. 评估框架

评估体系是这个项目最重要的部分之一。

系统不仅要能生成结果，还要证明结果是相对可靠的。

## 15.1 简历解析评估

### 目标

评估 Resume Agent 是否能正确从简历中提取信息。

### 数据集

- MVP 阶段准备 20 到 50 份简历
- 人工标注 ground truth
- 初期可以使用 synthetic resumes

### 指标

- Field Accuracy
- Skill Extraction Precision
- Skill Extraction Recall
- Education Extraction Accuracy
- Experience Extraction Accuracy

### 示例

真实技能：

```text
Python, Java, SQL, Docker
```

系统预测：

```text
Python, Java, React, SQL
```

则：

```text
Precision = 3 / 4
Recall = 3 / 4
```

## 15.2 JD 解析评估

### 目标

评估 JD Agent 是否能正确提取岗位要求。

### 指标

- Required skill extraction accuracy
- Preferred skill extraction accuracy
- Responsibility coverage
- Rubric consistency

## 15.3 匹配与排序评估

### 目标

评估系统对候选人的排序是否合理。

### 数据集

准备多个 JD 和候选人组。

示例：

- 5 个 JD
- 每个 JD 10 个候选人
- 人工标注适合的 Top candidates

### 指标

- Precision@K
- Recall@K
- NDCG@K
- Spearman rank correlation

### 解释

Precision@K 用来检查系统推荐的 Top K 候选人里，有多少是真正合适的。

NDCG@K 用来检查更合适的候选人是否排在更靠前的位置。

Spearman rank correlation 用来检查系统排序和人工排序是否接近。

## 15.4 RAG 证据评估

### 目标

评估系统给出的候选人评价是否被简历证据支持。

### 指标

- Context Precision
- Faithfulness
- Evidence Coverage
- Answer Relevance

### 示例

如果系统说：

```text
The candidate has RAG project experience.
```

那么系统必须提供来自简历的证据，例如：

```text
Built a local RAG system using Qdrant and FastAPI.
```

## 15.5 工作流评估

### 目标

评估 LangGraph 工作流是否能稳定运行。

### 指标

- Task Success Rate
- Invalid JSON Rate
- Tool Call Success Rate
- Average Latency
- Cost per Candidate
- Human Correction Rate
- Error Recovery Success Rate

### 示例报告

```text
Total resumes tested: 100
Successfully parsed resumes: 96
Resume parsing success rate: 96%
Invalid JSON outputs: 3
Matching workflow completion rate: 94%
Average processing time per candidate: 12 seconds
Average cost per candidate: 0.03 USD
```

## 16. 数据集计划

### 16.1 岗位描述数据

可能来源：

- 公开岗位描述
- Seek 岗位
- LinkedIn 岗位
- Kaggle job description datasets
- 手动编写 JD

第一版可以使用：

- 5 个岗位描述
- Software Engineer
- AI Engineer
- Data Analyst
- Backend Developer
- Machine Learning Engineer

### 16.2 简历数据

可能来源：

- 公开简历数据集
- Kaggle resume datasets
- 使用 LLM 生成的 synthetic resumes
- 手动创建的简历

重要规则：

不要使用未经许可的真实私人简历。  
如果使用真实简历，必须进行匿名化处理。

### 16.3 MVP 数据规模

第一版建议：

- 5 个 JD
- 30 份简历
- 每个 JD 5 到 10 个候选人

### 16.4 进阶数据规模

最终版可以扩展到：

- 20 个 JD
- 100 到 200 份简历
- 人工标注 Top candidates

## 17. 开发路线图

## Phase 1：MVP 工作流（已完成）

目标：

先构建最小完整闭环。

任务：

- 上传一个 JD
- 上传多份简历
- 解析 JD
- 解析简历
- 匹配候选人
- 生成排序结果

已交付：

- CLI + API demo
- 一个 JD 对应五份简历
- 候选人 ranking 输出

## Phase 2：结构化输出与数据存储（已完成）

目标：

让系统更稳定，更有工程化感觉。

任务：

- 添加 Pydantic schemas
- 添加 PostgreSQL
- 存储 candidate profiles
- 存储 JD profiles
- 存储 match results
- 添加错误处理

已交付：

- 稳定的后端数据 pipeline
- 结构化 JSON 输出
- 可持久化的结果存储

## Phase 3：RAG 证据检索（已完成）

目标：

让候选人评价变得可解释。

任务：

- 对简历进行 chunking
- 生成 embeddings
- 将 vectors 存入 Qdrant
- 根据 candidate_id 检索 evidence
- 将 evidence 附加到 match results 中

已交付：

- 基于证据的候选人匹配结果
- 简历解析后自动索引到 Qdrant
- 匹配前按候选人检索 RAG evidence

## Phase 4：LangGraph 多 Agent 工作流（已完成核心能力）

目标：

构建真正的 Multi-Agent 系统。

任务：

- 构建 JD Agent node
- 构建 Resume Agent node
- 构建 Retrieval node
- 构建 Match Agent node
- 构建 Ranking Agent node
- 构建 Interview Agent node
- 构建 Evaluation Agent node
- 构建 Email Agent node
- 添加 conditional routing
- 添加 human review nodes

已交付：

- LangGraph 工作流
- Shared state
- Conditional edges
- Human Review interrupt/resume
- Workflow API

## Phase 5：评估框架（已完成基础版）

目标：

证明系统质量。

任务：

- 构建 evaluation dataset
- 添加简历解析评估
- 添加 JD 解析评估
- 添加 ranking 评估
- 添加 RAG evidence 评估
- 添加 workflow reliability 评估
- 生成 evaluation report

已交付：

- Evaluation scripts
- Evaluation metrics
- JSON report
- Notebook 评估入口
- 51 个自动化测试覆盖 Agent、CRUD、API、端到端冒烟流程

## Phase 6：前端与 Demo（已完成 MVP）

目标：

让项目更适合面试展示。

任务：

- 构建 dashboard
- 构建岗位详情页
- 构建候选人排名页
- 构建候选人详情页
- 构建面试问题页
- 构建邮件草稿页

已交付：

- End-to-end demo
- GitHub README
- Next.js 前端工作台
- 岗位、简历、匹配与面试核心页面
- 可以写进简历并在面试中讲清楚的完整项目

## Phase 7：产品化稳定性（进行中）

目标：

提升真实使用时的稳定性、性能和可解释性。

已完成:

- Resume Agent 乱码清洗和语义错位修复
- Match Agent prompt 截断和输出限制
- LLM 精排失败时规则兜底评分
- 匹配结果按 `job_id + candidate_id` 更新，避免重复 Case
- 前端详情弹层、局部 loading、连续解析优化

后续:

- 前端错误提示细化，区分后端未启动、接口 500、LLM 截断等场景
- 匹配结果展示“兜底评分”标记，提醒 HR 人工复核
- 增加更多中文简历格式样例测试

## 18. 项目文件结构

```text
HireFlowAgents/
├── app/
│   ├── main.py                  # FastAPI 入口
│   ├── cli.py                   # CLI Demo
│   ├── api/
│   │   ├── jobs.py
│   │   ├── resumes.py
│   │   ├── matching.py
│   │   ├── interview.py
│   │   ├── evaluation.py
│   │   └── workflow.py
│   ├── agents/
│   │   ├── jd_agent.py
│   │   ├── resume_agent.py
│   │   ├── match_agent.py
│   │   ├── ranking_agent.py
│   │   ├── interview_agent.py
│   │   ├── evaluation_agent.py
│   │   └── email_agent.py
│   ├── graph/
│   │   ├── state.py
│   │   ├── workflow.py
│   │   └── nodes.py
│   ├── schemas/
│   │   ├── jd_schema.py
│   │   ├── resume_schema.py
│   │   ├── match_schema.py
│   │   ├── interview_schema.py
│   │   └── evaluation_schema.py
│   ├── services/
│   │   ├── document_loader.py
│   │   ├── embedding_service.py
│   │   ├── rag_service.py
│   │   ├── pre_screening.py
│   │   ├── vector_store.py
│   │   └── llm_service.py
│   ├── database/
│   │   ├── models.py
│   │   ├── session.py
│   │   └── crud.py
│   └── utils/
│       └── config.py
├── evaluation/
│   └── run_eval.py
├── frontend/
│   ├── pages/
│   ├── components/
│   ├── services/
│   └── types/
├── data/
├── logs/
├── tests/                      # 51 tests
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## 19. 项目技术亮点

本项目应该重点突出以下技术点：

1. 基于 LangGraph 的多 Agent 工作流
2. Shared state 状态管理
3. Conditional routing 条件路由
4. Human-in-the-loop 人工审核
5. 使用 Pydantic 进行结构化输出
6. 简历和 JD 文档解析
7. 基于 RAG 的证据检索
8. 基于 Rubric 的候选人评分
9. 带解释的候选人排序
10. 多维度评估框架
11. FastAPI 后端
12. 向量数据库集成
13. 前端 Dashboard
14. Docker 部署
15. LLM 本地/云端双模式
16. ThreadPool 并行精排与关键词粗筛
17. Resume Agent 原文规则解析与乱码防线
18. Match Agent 输出截断兜底与重复结果去重
19. 51 个自动化测试覆盖核心链路

## 20. 简历 Bullet Points

可以写进简历的英文 bullet points：

- Built HireFlow, a LangGraph-based multi-agent recruitment screening system that automates JD analysis, resume parsing, candidate matching, interview question generation, interview evaluation, and HR email drafting.

- Designed a controlled multi-agent workflow with JD Agent, Resume Agent, Match Agent, Ranking Agent, Interview Agent, Evaluation Agent, and Email Agent using LangGraph StateGraph and shared state management.

- Implemented structured information extraction with Pydantic schemas to convert unstructured resumes and job descriptions into reliable JSON profiles.

- Developed an evidence-based candidate ranking system using RAG, vector search, and rubric-based scoring to improve the explainability of AI-generated hiring recommendations.

- Built an evaluation framework covering resume parsing accuracy, skill extraction precision and recall, ranking quality with Precision@K and NDCG@K, RAG evidence faithfulness, and workflow success rate.

- Added human-in-the-loop review for candidate shortlisting and HR email drafting to reduce automation risk in hiring decisions.

## 21. 面试讲解思路

面试时可以按以下逻辑介绍这个项目：

第一，我发现招聘流程不是一个单一的 LLM 任务，而是一个多步骤 workflow，包括 JD 理解、简历解析、候选人匹配、排序、面试准备、面试评价和邮件沟通。

第二，我选择 LangGraph，而不是只用一个 prompt，因为这个项目需要一个可控的多 Agent 工作流，需要 shared state 和 conditional routing。

第三，我把系统拆成多个 specialized agents。每个 Agent 有明确职责，并且只更新全局 state 中对应的字段。

第四，我使用 RAG 让候选人评价变得 evidence-based。系统不会只说某个候选人合适，而是会展示简历中哪一部分支持这个判断。

第五，我设计了评估框架，分别评估 parsing quality、ranking quality、RAG evidence quality 和 workflow stability。

第六，我在真实联调中补了稳定性防线：Resume Agent 不完全依赖 LLM，而是结合原文规则解析；Match Agent 会控制 prompt/token 成本，并在 LLM 精排失败时给出规则兜底评分。

## 22. 风险与限制

本项目存在以下风险和限制：

1. LLM 输出可能不稳定
2. 复杂 PDF 格式可能导致简历解析失败
3. 候选人评分可能存在偏见
4. Synthetic data 不一定完全代表真实招聘场景
5. 评估需要人工标注数据
6. 邮件生成必须经过人工审核
7. 系统不能自动做最终招聘决定
8. 本地模型能力和上下文长度有限，需要控制 prompt 和输出长度
9. 复杂中文简历格式仍需要继续补充规则样例

## 23. 后续改进方向

未来可以继续扩展：

1. 增加 reranking，提高证据检索质量
2. 增加 OCR，支持扫描版简历
3. 增加 bias detection
4. 增加候选人对比页面
5. 增加面试语音转文字功能
6. 接入 LangSmith 做 tracing 和 monitoring
7. 支持不同岗位的定制评分 Rubric
8. 支持多语言简历
9. 使用 Docker 和云服务进行部署
10. 增加用户登录和权限管理
11. 增加匹配结果缓存，避免同一岗位重复匹配重复调用 LLM
12. 在前端标记“LLM 兜底评分”，方便 HR 人工复核

## 24. 最终项目范围

当前第一版完整项目已经完成：

- JD 解析
- 简历解析
- 候选人匹配
- 候选人排序
- RAG 证据检索
- LangGraph 工作流
- Human-in-the-loop interrupt/resume
- 面试问题生成
- 面试评价
- 邮件草稿生成与人工审批
- Next.js 前端工作台
- 评估脚本和 51 个自动化测试

后续重点不再是补齐流程，而是继续提高稳定性、评估质量和真实产品体验。

## 25. 项目总结

HireFlow 是一个比较适合校招简历的项目，因为它结合了 LLM 应用开发、RAG、多 Agent 工作流、结构化输出、评估体系和后端工程化能力。

这个项目最重要的价值是：它不是一个简单的 AI demo，而是一个基于 workflow 的系统，能够模拟真实业务流程。

最强的五个卖点是：

1. 基于 LangGraph 的多 Agent 工作流
2. 基于 RAG 证据的候选人排序
3. 面试问题、评价、邮件草稿的完整后续流程
4. 面向真实联调问题的稳定性防线
5. 完整的评估和测试体系

现在这个项目已经可以作为一个比较完整的校招简历项目进行展示，后续主要围绕更真实的数据集、更细的评估指标和更好的前端体验继续增强。

---

## 26. 技术栈最终选型 (2026-05-31 更新)

以下为 MVP Phase 1 确认的技术栈，替代本文档前 25 节中的初步建议。

| 层级 | 选型 | 备注 |
|---|---|---|
| 关系型数据库 | **PostgreSQL** | 替代原 SQLite 规划 |
| 向量数据库 | **Qdrant** | 替代原 Chroma 规划 |
| LLM Provider | **DeepSeek API (云端) + LM Studio (本地)** | 双模式, OpenAI 兼容接口一键切换 |
| Embedding | **DeepSeek (云端) + LM Studio (本地)** | 与 LLM 同步切换 |
| 结构化输出 | **LangChain with_structured_output** | 与 Pydantic 深度集成 |
| PDF 解析 | **LangChain Document Loaders** | 统一接口 |
| DOCX 解析 | **python-docx** | 不变 |
| 文本切分 | **RecursiveCharacterTextSplitter** | 后续升级语义切分 |
| LangGraph 持久化 | **PostgresSaver** | 支持中断恢复和 Human-in-the-loop |
| 配置管理 | **Pydantic Settings** | 类型安全 + 自动验证 |
| 前端 | **Next.js + Tailwind CSS** | 不变 |
| 部署 | **Docker Compose** (API + PostgreSQL + Qdrant) | 多服务编排 |

详见:
- `logs/技术栈选择原因.md` — 每个选型的"为什么选这个而不选那个"
- `logs/MVPs/MVP-Phase1-计划.md` — MVP 阶段详细计划
