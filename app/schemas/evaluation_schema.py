"""
app/schemas/evaluation_schema.py
=================================
面试评价和邮件相关的 Pydantic 数据模型。

定义了 Interview Agent、Evaluation Agent 和 Email Agent 输出的数据结构。
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict


class InterviewQuestion(BaseModel):
    """
    单条面试问题。

    Interview Agent 为候选人定制的面试题目。
    """

    # 问题类型: "technical"(技术), "project_deep_dive"(项目深挖),
    #           "behavioral"(行为), "risk_verification"(风险验证)
    type: str = Field(..., description="问题类型")

    # 问题正文
    question: str = Field(..., description="面试问题")

    # 提问目的: 面试官想通过这个问题了解什么
    purpose: str = Field(..., description="提问目的")


class CandidateQuestions(BaseModel):
    """
    单个候选人的完整面试问题集。
    """

    # 候选人 ID
    candidate_id: str = Field(..., description="候选人ID")

    # 为该候选人生成的所有面试问题
    questions: List[InterviewQuestion] = Field(
        default_factory=list, description="面试问题列表"
    )


class InterviewEvaluation(BaseModel):
    """
    面试评价 (面试后填写)。

    Evaluation Agent 根据面试记录给出的最终评价。
    """

    # 候选人 ID
    candidate_id: str = Field(..., description="候选人ID")

    # 面试总结: 对候选人面试表现的整体概述
    summary: str = Field(..., description="面试表现总结")

    # 技术深度评分 (1-10)
    technical_depth: int = Field(..., ge=1, le=10, description="技术深度 (1-10)")

    # 沟通表达评分 (1-10)
    communication: int = Field(..., ge=1, le=10, description="沟通表达 (1-10)")

    # 问题解决能力评分 (1-10)
    problem_solving: int = Field(..., ge=1, le=10, description="问题解决能力 (1-10)")

    # 之前识别出的风险点是否在面试中被解决
    risks_resolved: List[str] = Field(
        default_factory=list, description="已解决的风险点"
    )

    # 仍然存在的顾虑
    remaining_concerns: List[str] = Field(
        default_factory=list, description="遗留顾虑"
    )

    # 最终推荐: "Strongly Recommend" / "Recommend" / "Not Recommend"
    final_recommendation: str = Field(..., description="最终推荐")


class EmailDraft(BaseModel):
    """
    HR 邮件草稿。

    Email Agent 生成的邮件草稿，发送前必须经过人工审核。
    """

    # 邮件 ID (系统生成)
    email_id: str = Field(..., description="邮件唯一ID")

    # 候选人 ID
    candidate_id: str = Field(..., description="候选人ID")

    # 岗位 ID
    job_id: str = Field(..., description="岗位ID")

    # 邮件类型: "interview_invite"(面试邀请) / "rejection"(拒信)
    #            "follow_up"(跟进) / "next_round"(下一轮通知)
    email_type: str = Field(..., description="邮件类型")

    # 邮件标题
    subject: str = Field(..., description="邮件标题")

    # 邮件正文
    body: str = Field(..., description="邮件正文")

    # 邮件状态: "draft"(草稿) / "approved"(已批准) / "rejected"(已拒绝)
    status: str = Field(default="draft", description="邮件状态")
