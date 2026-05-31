"""
app/schemas/match_schema.py
============================
候选人匹配评分相关的 Pydantic 数据模型。

定义了 Match Agent 输出的匹配结果格式。
包含各维度分数、支撑证据和最终推荐。
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional


class Evidence(BaseModel):
    """
    评分支撑证据。

    每个评分断言都应该有一条证据支持。
    证据来自候选人的简历原文 (通过 RAG 检索获得)。
    """

    # 评分中的断言，例如 "候选人具备 RAG 项目经验"
    claim: str = Field(..., description="评分断言")

    # 证据来源，例如简历的第 2 页
    source: str = Field(..., description="证据来源 (如 resume_page_2)")

    # 简历原文片段，用于支撑 claim 的真实性
    text: str = Field(..., description="简历原文摘录")


class DimensionScores(BaseModel):
    """
    各维度评分明细。

    按照 JD 中定义的 Rubric 权重，对候选人在每个维度上的表现打分。
    """

    # 技术技能匹配得分
    technical_skills: float = Field(..., description="技术技能得分")

    # 项目相关性得分
    project_relevance: float = Field(..., description="项目相关性得分")

    # 工作经验得分
    experience: float = Field(..., description="工作经验得分")

    # 教育背景得分
    education: float = Field(..., description="教育背景得分")

    # 领域相关性得分
    domain_relevance: float = Field(..., description="领域相关性得分")

    # 沟通表达得分 (从简历质量推断)
    communication: float = Field(..., description="沟通表达得分")

    # 风险扣分 (负数，如 -5 表示扣了 5 分)
    risk_penalty: float = Field(default=0.0, description="风险扣分")


class MatchResult(BaseModel):
    """
    单个候选人的匹配评分结果。

    Match Agent 比较 JD 要求和候选人简历后输出的完整评分报告。
    """

    # 候选人 ID
    candidate_id: str = Field(..., description="候选人ID")

    # 总分: 各维度得分之和 (包含 risk_penalty)
    # 由各维度分数计算得出，不需要 LLM 生成
    total_score: float = Field(..., description="总匹配分数")

    # 各维度详细得分
    dimension_scores: DimensionScores = Field(..., description="各维度得分")

    # 候选人优势列表，基于简历证据总结
    strengths: List[str] = Field(
        default_factory=list, description="候选人优势"
    )

    # 风险点列表
    risks: List[str] = Field(default_factory=list, description="风险点")

    # 支撑评分结论的简历证据列表
    evidence: List[Evidence] = Field(
        default_factory=list, description="评分证据"
    )

    # 推荐等级: "Strong Match" / "Medium Match" / "Weak Match" / "Not Recommended"
    recommendation: str = Field(..., description="推荐等级")

    # 匹配总结: 1-2 句对整体匹配情况的文字描述
    summary: Optional[str] = Field(default=None, description="匹配总结")


class RankingResult(BaseModel):
    """
    候选人排序结果。

    Ranking Agent 对所有候选人按总分排序后的输出。
    """

    # 排序后的候选人列表，从高到低排列
    ranked_candidates: List[MatchResult] = Field(
        default_factory=list, description="排序后的候选人列表"
    )

    # shortlist: 推荐进入面试的候选人 ID 列表
    shortlist: List[str] = Field(
        default_factory=list, description="Shortlist 推荐名单"
    )

    # 排序解释: 1-2 句话说明为什么这样排名
    explanation: Optional[str] = Field(
        default=None, description="排序解释"
    )
