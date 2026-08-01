"""
app/schemas/evaluation_schema.py
================================
面试、评价和邮件流程使用的结构化输出模型。

这些模型会交给 LangChain 的 with_structured_output()，让模型直接返回
经过 Pydantic 校验的数据，避免把不规范 JSON 原文展示给用户。
"""

from typing import List, Literal

from pydantic import BaseModel, Field


class InterviewQuestion(BaseModel):
    """Interview Agent 为候选人生成的一条面试问题。"""

    # 问题类型，例如 technical 或 project_deep_dive。
    type: str = Field(..., description="问题类型")
    # question 是最终展示给面试官的题目正文。
    question: str = Field(..., description="面试问题")
    # purpose 解释为什么要问这道题。
    purpose: str = Field(..., description="提问目的")


class CandidateQuestions(BaseModel):
    """单个候选人的完整面试问题集。"""

    candidate_id: str = Field(..., description="候选人ID")
    questions: List[InterviewQuestion] = Field(default_factory=list, description="面试问题列表")


class InterviewEvaluation(BaseModel):
    """保留给旧工作流使用的面试评价结构。"""

    candidate_id: str = Field(..., description="候选人ID")
    summary: str = Field(..., description="面试表现总结")
    technical_depth: int = Field(..., ge=1, le=10, description="技术深度")
    communication: int = Field(..., ge=1, le=10, description="沟通表达")
    problem_solving: int = Field(..., ge=1, le=10, description="问题解决能力")
    risks_resolved: List[str] = Field(default_factory=list, description="已解决的风险点")
    remaining_concerns: List[str] = Field(default_factory=list, description="遗留顾虑")
    final_recommendation: str = Field(..., description="最终推荐")


class EmailDraft(BaseModel):
    """保留给旧工作流使用、且必须经人工审批的邮件草稿结构。"""

    email_id: str = Field(..., description="邮件唯一ID")
    candidate_id: str = Field(..., description="候选人ID")
    job_id: str = Field(..., description="岗位ID")
    email_type: str = Field(..., description="邮件类型")
    subject: str = Field(..., description="邮件标题")
    body: str = Field(..., description="邮件正文")
    status: str = Field(default="draft", description="邮件状态")


class RiskResolution(BaseModel):
    """记录一个匹配风险在面试中是否得到解释。"""

    # risk 是匹配阶段已经识别出的风险名称。
    risk: str = Field(..., description="需要核实的风险")
    # status 只能使用这三个固定值，防止前端收到随意文本。
    status: Literal["resolved", "partially_resolved", "unresolved"] = Field(
        ..., description="风险解决状态"
    )
    # reason 必须根据面试官反馈解释判断依据。
    reason: str = Field(..., description="风险状态的中文说明")


class InterviewEvaluationOutput(BaseModel):
    """Evaluation Agent 返回的完整结构化评价。"""

    # 三项分数都限制在 1-10，超出范围时 Pydantic 会拒绝脏数据。
    technical_depth_score: int = Field(..., ge=1, le=10, description="技术深度分数")
    communication_score: int = Field(..., ge=1, le=10, description="沟通表达分数")
    problem_solving_score: int = Field(..., ge=1, le=10, description="问题解决分数")
    risk_resolution: list[RiskResolution] = Field(default_factory=list, description="风险核实结果")
    strengths: list[str] = Field(default_factory=list, description="面试亮点")
    concerns: list[str] = Field(default_factory=list, description="需要关注的问题")
    summary: str = Field(..., description="一到两句中文面试总结")
    recommendation: Literal[
        "Strongly Recommend", "Recommend", "Hold", "Not Recommend"
    ] = Field(..., description="供人工审核的建议")
    # 招聘属于高风险决策，这个字段无论模型如何输出都必须保持为 True。
    requires_human_review: bool = Field(default=True, description="是否需要人工审核")
