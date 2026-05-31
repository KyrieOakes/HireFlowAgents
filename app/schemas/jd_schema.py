"""
app/schemas/jd_schema.py
=========================
岗位描述 (JD) 相关的 Pydantic 数据模型。

Pydantic 用于定义结构化输出的"模板"。
当你要求 LLM 返回 JSON 时，Pydantic 可以:
1. 定义每个字段的名称、类型和描述
2. 自动验证 LLM 返回的 JSON 是否符合格式
3. 提供默认值和必填项检查

这些 Schema 是连接 LLM 非结构化输出和系统结构化数据的桥梁。
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class JobDescription(BaseModel):
    """
    岗位描述的完整结构化信息。

    这个类定义了 JD Agent 解析岗位描述后应该输出的格式。
    每个字段都来自真实招聘场景中 JD 包含的信息。
    """

    # 岗位名称，例如 "初级 AI 工程师", "Python 后端开发"
    # Field(..., description="...") 中的 ... 表示此字段是必填的
    job_title: str = Field(..., description="岗位名称")

    # 必备技能列表: 候选人必须掌握的技能
    # List[str] 表示这是一个字符串列表，例如 ["Python", "SQL", "Docker"]
    required_skills: List[str] = Field(
        default_factory=list, description="必备技能列表"
    )

    # 加分技能列表: 候选人掌握会更好但不是必须的技能
    preferred_skills: List[str] = Field(
        default_factory=list, description="加分技能列表"
    )

    # 岗位职责: 入职后需要承担的主要工作内容
    responsibilities: List[str] = Field(
        default_factory=list, description="岗位职责列表"
    )

    # 学历要求列表，例如 ["计算机科学或相关专业本科"]
    education_requirements: List[str] = Field(
        default_factory=list, description="学历要求列表"
    )

    # 经验要求: 需要的工作年限范围，例如 "0-2年"、"3-5年"
    experience_requirements: Optional[str] = Field(
        default=None, description="经验年限要求"
    )

    # 公司名称 (如果 JD 中提及)
    company: Optional[str] = Field(default=None, description="公司名称")

    # 工作地点
    location: Optional[str] = Field(default=None, description="工作地点")

    # 技术栈要求: 具体的技术和框架，例如 ["FastAPI", "PostgreSQL", "Docker"]
    technical_requirements: List[str] = Field(
        default_factory=list, description="技术要求列表"
    )

    # 软技能要求: 例如沟通能力、团队协作等
    soft_skills: List[str] = Field(
        default_factory=list, description="软技能要求列表"
    )


class ScoringRubric(BaseModel):
    """
    候选人评分 Rubric (评分标准)。

    定义了 Match Agent 对候选人评分的各维度权重。
    总分 100 分，各维度分数之和 = 100。
    风险扣分是额外的负分项。
    """

    # 技术技能匹配 (满分 30): 候选人的技术栈和岗位要求的匹配度
    technical_skills: int = Field(default=30, description="技术技能匹配 (满分30)")

    # 项目相关性 (满分 20): 候选人过往项目经验与岗位职责的相关程度
    project_relevance: int = Field(default=20, description="项目相关性 (满分20)")

    # 经验 (满分 15): 工作和实习经验的匹配程度
    experience: int = Field(default=15, description="工作经验 (满分15)")

    # 教育背景 (满分 10): 学历和专业与岗位要求的相关性
    education: int = Field(default=10, description="教育背景 (满分10)")

    # 领域相关性 (满分 10): 候选人是否在相关行业或领域有经验
    domain_relevance: int = Field(default=10, description="领域相关性 (满分10)")

    # 沟通表达 (满分 5): 从简历文字表达、项目描述清晰度等推断 (间接指标)
    communication: int = Field(default=5, description="沟通表达 (满分5)")

    # 风险扣分 (最多 -10): 识别到的风险点，如经验不足、频繁跳槽等
    risk_penalty: int = Field(default=-10, description="风险扣分 (最多-10)")
