"""
app/database/models.py
=======================
SQLAlchemy ORM 数据模型定义。
把Python 的类 映射为“数据库的表” 的技术，就叫做 ORM-对象关系映射

数据库中每个表对应一个 Python 类。每行记录对应一个类实例。
SQLAlchemy 会自动把 Python 对象操作翻译为 SQL 语句，
不需要手写 SQL。

使用方法:
from app.database.models import Job
new_job = Job(title="Python工程师", jd_text="...")
db.add(new_job)
db.commit()
"""

import uuid
import datetime
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database.session import Base


# ---- 辅助函数: 生成唯一 ID ----
# uuid.uuid4() 生成一个随机的全局唯一标识符
# 格式如 "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
# 用前8位作为短ID，如 "a1b2c3d4"
def _gen_id() -> str:
    return uuid.uuid4().hex[:8]


def _now() -> datetime.datetime:
    """返回当前 UTC 时间。"""
    return datetime.datetime.now(datetime.timezone.utc)


# ============================================================
# 1. 岗位表 (jobs)
# ============================================================

class Job(Base):
    """
    岗位信息表。

    存储原始岗位描述和 JD Agent 解析后的结构化结果。
    """

    # __tablename__: 数据库中实际的表名
    __tablename__ = "jobs"

    # 主键列: 每个岗位的唯一标识
    # primary_key=True 表示这是主键，数据库会自动建立索引
    # default=_gen_id 每次创建新记录时自动生成ID
    job_id = Column(String, primary_key=True, default=_gen_id)

    # 岗位名称 (从 JD 中提取)
    title = Column(String, nullable=True)

    # 公司名称 (从 JD 中提取)
    company = Column(String, nullable=True)

    # 原始岗位描述全文 (用户上传的原始文本)
    jd_text = Column(Text, nullable=False)

    # JD Agent 解析后的结构化结果，存储为 JSON 字符串
    # JSON 类型在 PostgreSQL 中是 jsonb，可以高效查询
    jd_profile_json = Column(JSON, nullable=True)

    # 评分 Rubric (各维度权重)
    rubric_json = Column(JSON, nullable=True)

    # 创建时间
    # default=_now: 自动填入当前时间
    created_at = Column(DateTime, default=_now)

    # 建立与候选人表的关联 (通过中间表 match_results)
    # back_populates 指定对方表中的属性名，形成双向关联
    # cascade="all, delete-orphan": 删除岗位时，相关匹配结果也自动删除
    match_results = relationship(
        "MatchResult",
        back_populates="job",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        """对象的字符串表示，调试时有用。"""
        return f"<Job(job_id={self.job_id}, title={self.title})>"


# ============================================================
# 2. 候选人表 (candidates)
# ============================================================

class Candidate(Base):
    """
    候选人信息表。

    存储原始简历文本和 Resume Agent 解析后的结构化画像。
    """

    __tablename__ = "candidates"

    # 候选人唯一ID
    candidate_id = Column(String, primary_key=True, default=_gen_id)

    # 姓名 (从简历中提取)
    name = Column(String, nullable=True)

    # 邮箱 (从简历中提取)
    email = Column(String, nullable=True)

    # 简历文件名 (原始上传的文件名)
    resume_filename = Column(String, nullable=True)

    # 原始简历文本 (从 PDF/DOCX 提取后的纯文本)
    resume_text = Column(Text, nullable=False)

    # Resume Agent 解析后的结构化画像，存储为 JSON
    profile_json = Column(JSON, nullable=True)

    # 创建时间
    created_at = Column(DateTime, default=_now)

    # 关联
    resume_chunks = relationship(
        "ResumeChunk",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )
    match_results = relationship(
        "MatchResult",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Candidate(candidate_id={self.candidate_id}, name={self.name})>"


# ============================================================
# 3. 简历文本块表 (resume_chunks)
# ============================================================

class ResumeChunk(Base):
    """
    简历文本块表。

    将简历切分为小块后，每块存储在这里。
    chunk 对应的 embedding 向量存在 Qdrant 中，
    这里只存 Qdrant 中的 point ID 和文本元数据。
    """

    __tablename__ = "resume_chunks"

    # chunk 唯一ID
    chunk_id = Column(String, primary_key=True, default=_gen_id)

    # 所属候选人 (外键关联 candidates 表)
    # ForeignKey("candidates.candidate_id") 表示这列的值必须存在于 candidates 表中
    candidate_id = Column(
        String,
        ForeignKey("candidates.candidate_id"),
        nullable=False,
    )

    # chunk 的原始文本内容
    text = Column(Text, nullable=False)

    # 在 Qdrant 中的 point ID (用于关联向量)
    qdrant_point_id = Column(String, nullable=True)

    # 该 chunk 来自原始文档的第几页 (PDF 才有效，其他格式填 0)
    page_number = Column(Integer, default=0)

    # 来源文件名
    source = Column(String, nullable=True)

    # 创建时间
    created_at = Column(DateTime, default=_now)

    # 关联回候选人
    candidate = relationship("Candidate", back_populates="resume_chunks")

    def __repr__(self):
        return f"<ResumeChunk(id={self.chunk_id}, candidate={self.candidate_id})>"


# ============================================================
# 4. 匹配结果表 (match_results)
# ============================================================

class MatchResult(Base):
    """
    候选人匹配评分结果表。

    存储 Match Agent 对每个候选人 × 岗位组合的评分。
    """

    __tablename__ = "match_results"

    # 匹配结果唯一ID
    match_id = Column(String, primary_key=True, default=_gen_id)

    # 关联的岗位
    job_id = Column(
        String,
        ForeignKey("jobs.job_id"),
        nullable=False,
    )

    # 关联的候选人
    candidate_id = Column(
        String,
        ForeignKey("candidates.candidate_id"),
        nullable=False,
    )

    # 总匹配分数 (0-100)
    total_score = Column(Float, default=0.0)

    # 各维度详细分数 (JSON 格式)
    # 例如: {"technical_skills": 27, "project_relevance": 18, ...}
    dimension_scores_json = Column(JSON, nullable=True)

    # 支撑评分的证据列表 (JSON 格式)
    evidence_json = Column(JSON, nullable=True)

    # 识别到的风险点列表 (JSON 格式)
    risk_json = Column(JSON, nullable=True)

    # 候选人优势列表
    strengths_json = Column(JSON, nullable=True)

    # 推荐等级: "Strong Match" / "Medium Match" / "Weak Match" / "Not Recommended"
    recommendation = Column(String, nullable=True)

    # 匹配总结
    summary = Column(Text, nullable=True)

    # 创建时间
    created_at = Column(DateTime, default=_now)

    # 关联回岗位和候选人
    # 注意: 因为 Job 和 Candidate 的 relationship 也指向 MatchResult，
    # 这里 back_populates 中填的 "match_results" 必须和对方类中的属性名一致
    job = relationship("Job", back_populates="match_results")
    candidate = relationship("Candidate", back_populates="match_results")

    def __repr__(self):
        return f"<MatchResult(job={self.job_id}, candidate={self.candidate_id}, score={self.total_score})>"


# ============================================================
# 5-7. 面试相关表 (Phase 1.2 实现，先定义骨架)
# ============================================================

class InterviewQuestion(Base):
    """面试问题表 (Phase 1.2)"""
    __tablename__ = "interview_questions"

    question_id = Column(String, primary_key=True, default=_gen_id)
    job_id = Column(String, ForeignKey("jobs.job_id", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(String, ForeignKey("candidates.candidate_id", ondelete="CASCADE"), nullable=False)
    question_type = Column(String, nullable=True)
    question = Column(Text, nullable=True)
    purpose = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now)


class InterviewEvaluation(Base):
    """面试评价表 (Phase 1.2)"""
    __tablename__ = "interview_evaluations"

    evaluation_id = Column(String, primary_key=True, default=_gen_id)
    candidate_id = Column(String, ForeignKey("candidates.candidate_id", ondelete="CASCADE"), nullable=False)
    job_id = Column(String, ForeignKey("jobs.job_id", ondelete="CASCADE"), nullable=False)
    feedback_text = Column(Text, nullable=True)
    evaluation_json = Column(JSON, nullable=True)
    final_recommendation = Column(String, nullable=True)
    created_at = Column(DateTime, default=_now)


class EmailDraft(Base):
    """邮件草稿表 (Phase 1.2)"""
    __tablename__ = "email_drafts"

    email_id = Column(String, primary_key=True, default=_gen_id)
    candidate_id = Column(String, ForeignKey("candidates.candidate_id", ondelete="CASCADE"), nullable=False)
    job_id = Column(String, ForeignKey("jobs.job_id", ondelete="CASCADE"), nullable=False)
    email_type = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    body = Column(Text, nullable=True)
    status = Column(String, default="draft")
    created_at = Column(DateTime, default=_now)
