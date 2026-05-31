"""
app/schemas/resume_schema.py
=============================
候选人简历相关的 Pydantic 数据模型。

定义了 Resume Agent 解析简历后输出的结构化格式。
每个字段对应简历中常见的一个信息块。
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class Education(BaseModel):
    """
    教育经历。

    记录一段完整的教育经历，包括学位、学校、专业和时间。
    """

    # 学位: 例如 "硕士"、"学士"、"博士"
    degree: str = Field(..., description="学位")

    # 学校名称
    school: str = Field(..., description="学校名称")

    # 专业方向
    major: str = Field(..., description="专业")

    # 入学年份 (可选，有些简历没有)
    start_year: Optional[int] = Field(default=None, description="入学年份")

    # 毕业年份 (可选)
    end_year: Optional[int] = Field(default=None, description="毕业年份")


class Project(BaseModel):
    """
    项目经历。

    候选人参与过的一个项目的详细信息。
    """

    # 项目名称
    name: str = Field(..., description="项目名称")

    # 项目描述: 1-2 句话概括项目做了什么
    description: str = Field(..., description="项目描述")

    # 在项目中使用的技术栈
    technologies: List[str] = Field(
        default_factory=list, description="使用的技术"
    )

    # 候选人在项目中担任的角色或负责的部分
    role: Optional[str] = Field(default=None, description="项目角色")


class WorkExperience(BaseModel):
    """
    工作或实习经历。

    记录一段完整的工作经历。
    """

    # 公司名称
    company: str = Field(..., description="公司名称")

    # 职位名称
    title: str = Field(..., description="职位名称")

    # 工作起止时间，例如 "2023.06 - 2024.12"
    duration: Optional[str] = Field(default=None, description="起止时间")

    # 主要工作内容和成果
    description: List[str] = Field(
        default_factory=list, description="工作内容列表"
    )


class CandidateProfile(BaseModel):
    """
    候选人完整画像。

    Resume Agent 解析简历后输出的标准化格式。
    包含了招聘决策所需的候选人全部信息。
    """

    # 候选人唯一 ID，系统生成的标识符
    candidate_id: str = Field(..., description="候选人唯一ID")

    # 候选人姓名
    name: str = Field(..., description="候选人姓名")

    # 候选人邮箱 (从简历中提取)
    email: Optional[str] = Field(default=None, description="邮箱地址")

    # 电话 (从简历中提取)
    phone: Optional[str] = Field(default=None, description="电话号码")

    # 教育经历列表，一个候选人可能有多段教育经历
    education: List[Education] = Field(
        default_factory=list, description="教育经历列表"
    )

    # 技能列表，例如 ["Python", "Docker", "SQL", "FastAPI"]
    skills: List[str] = Field(default_factory=list, description="技能列表")

    # 项目经历列表
    projects: List[Project] = Field(
        default_factory=list, description="项目经历列表"
    )

    # 工作或实习经历列表
    work_experience: List[WorkExperience] = Field(
        default_factory=list, description="工作或实习经历列表"
    )

    # 证书或认证列表
    certifications: List[str] = Field(
        default_factory=list, description="证书列表"
    )

    # ---- 分析性字段 (由 Agent 推理得出，非直接提取) ----

    # 候选人优势: Resume Agent 在分析后总结的候选人亮点
    strengths: List[str] = Field(
        default_factory=list, description="候选人优势"
    )

    # 候选人风险点: 如经验不足、技能缺口、经历断层等
    risks: List[str] = Field(
        default_factory=list, description="风险点"
    )

    # 缺失信息: 简历中没有提及但对招聘决策重要的信息
    missing_info: List[str] = Field(
        default_factory=list, description="缺失信息"
    )

    # 经验年限估计: 从工作经历推算出的总经验年限
    estimated_years_of_experience: Optional[float] = Field(
        default=None, description="估计经验年限"
    )
