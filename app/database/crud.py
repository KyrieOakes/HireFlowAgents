"""
app/database/crud.py
=====================
数据库 CRUD 操作函数。

CRUD = Create (创建) + Read (读取) + Update (更新) + Delete (删除)
每个函数封装一条或多条数据库操作。

所有函数都接收 db 参数 (SQLAlchemy 会话)，
由调用方负责管理会话的生命周期。
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from app.database import models


# ============================================================
# 岗位 (Job) CRUD
# ============================================================

def create_job(db: Session, jd_text: str, title: str = None) -> models.Job:
    """
    创建新岗位记录。

    参数:
        db: 数据库会话
        jd_text: 原始岗位描述全文
        title: 岗位名称 (可选，解析后会更新)
    返回:
        Job: 新创建的岗位对象 (已写入数据库)
    """
    # 创建 Job 实例
    job = models.Job(
        jd_text=jd_text,
        title=title,
    )
    # db.add(): 将新对象加入会话的待提交列表
    db.add(job)
    # db.commit(): 将待提交的改动写入数据库
    db.commit()
    # db.refresh(): 从数据库重新加载该对象 (获取数据库自动生成的字段)
    db.refresh(job)
    return job


def get_job(db: Session, job_id: str) -> Optional[models.Job]:
    """
    按 ID 查询岗位。

    参数:
        db: 数据库会话
        job_id: 岗位唯一ID
    返回:
        Job 或 None (找不到时)
    """
    # db.query(Model).filter(条件).first(): 查询并返回第一条匹配记录
    return db.query(models.Job).filter(models.Job.job_id == job_id).first()


def get_all_jobs(db: Session) -> List[models.Job]:
    """获取所有岗位列表。"""
    return db.query(models.Job).order_by(models.Job.created_at.desc()).all()


def update_job_profile(
    db: Session, job_id: str, jd_profile: dict, rubric: dict = None
) -> Optional[models.Job]:
    """
    更新岗位的结构化解析结果。

    在 JD Agent 解析完成后调用，将结果保存到数据库。

    参数:
        db: 数据库会话
        job_id: 岗位ID
        jd_profile: JD Agent 解析出的结构化信息 (字典)
        rubric: 评分 Rubric (字典, 可选)
    返回:
        Job 或 None
    """
    job = get_job(db, job_id)
    if job:
        # 将 Python 字典直接存入 JSON 列
        job.jd_profile_json = jd_profile
        if rubric:
            job.rubric_json = rubric
        if jd_profile.get("job_title"):
            job.title = jd_profile["job_title"]
        db.commit()
        db.refresh(job)
    return job


# ============================================================
# 候选人 (Candidate) CRUD
# ============================================================

def create_candidate(
    db: Session,
    resume_text: str,
    name: str = None,
    email: str = None,
    filename: str = None,
) -> models.Candidate:
    """
    创建新候选人记录。

    参数:
        db: 数据库会话
        resume_text: 从简历文件中提取的纯文本
        name: 姓名 (可选，解析后会更新)
        email: 邮箱 (可选)
        filename: 原始文件名
    返回:
        Candidate: 新创建的候选人对象
    """
    candidate = models.Candidate(
        resume_text=resume_text,
        name=name,
        email=email,
        resume_filename=filename,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


def get_candidate(db: Session, candidate_id: str) -> Optional[models.Candidate]:
    """按 ID 查询候选人。"""
    return (
        db.query(models.Candidate)
        .filter(models.Candidate.candidate_id == candidate_id)
        .first()
    )


def get_all_candidates(db: Session) -> List[models.Candidate]:
    """获取所有候选人列表。"""
    return (
        db.query(models.Candidate)
        .order_by(models.Candidate.created_at.desc())
        .all()
    )


def update_candidate_profile(
    db: Session, candidate_id: str, profile: dict
) -> Optional[models.Candidate]:
    """
    更新候选人的结构化画像。

    在 Resume Agent 解析完成后调用。

    参数:
        db: 数据库会话
        candidate_id: 候选人ID
        profile: 结构化画像 (字典)
    返回:
        Candidate 或 None
    """
    candidate = get_candidate(db, candidate_id)
    if candidate:
        candidate.profile_json = profile
        # 保护自动命名的申请人: 如果名字以"申请人"开头 (系统自动生成),
        # 说明原始简历中没有真实姓名, 不要被 LLM 从简历中提取的名字覆盖
        is_auto_named = candidate.name and candidate.name.startswith("申请人")
        if profile.get("name") and not is_auto_named:
            candidate.name = profile["name"]
        if profile.get("email"):
            candidate.email = profile["email"]
        db.commit()
        db.refresh(candidate)
    return candidate


# ============================================================
# 简历文本块 (ResumeChunk) CRUD
# ============================================================

def save_resume_chunks(
    db: Session,
    candidate_id: str,
    chunks: list,
    qdrant_point_ids: list = None,
) -> List[models.ResumeChunk]:
    """
    保存简历的文本块记录。

    在文档切分并存入 Qdrant 后调用，记录 chunk → Qdrant point 的映射。

    参数:
        db: 数据库会话
        candidate_id: 所属候选人ID
        chunks: Document 对象列表 (来自 document_loader)
        qdrant_point_ids: Qdrant point ID 列表 (与 chunks 一一对应)
    返回:
        List[ResumeChunk]: 创建的 chunk 记录
    """
    db_chunks = []
    for i, doc in enumerate(chunks):
        chunk = models.ResumeChunk(
            candidate_id=candidate_id,
            text=doc.page_content,
            page_number=doc.metadata.get("page", 0),
            source=doc.metadata.get("source", ""),
            qdrant_point_id=qdrant_point_ids[i] if qdrant_point_ids else None,
        )
        db.add(chunk)
        db_chunks.append(chunk)

    db.commit()
    return db_chunks


def get_chunks_by_candidate(
    db: Session, candidate_id: str
) -> List[models.ResumeChunk]:
    """获取某个候选人的所有简历文本块。"""
    return (
        db.query(models.ResumeChunk)
        .filter(models.ResumeChunk.candidate_id == candidate_id)
        .all()
    )


# ============================================================
# 匹配结果 (MatchResult) CRUD
# ============================================================

def save_match_result(
    db: Session,
    job_id: str,
    candidate_id: str,
    total_score: float,
    dimension_scores: dict,
    evidence: list,
    risks: list,
    strengths: list,
    recommendation: str,
    summary: str = None,
) -> models.MatchResult:
    """
    保存候选人匹配评分结果。

    参数:
        db: 数据库会话
        job_id: 岗位ID
        candidate_id: 候选人ID
        total_score: 总分
        dimension_scores: 各维度得分
        evidence: 支撑证据列表
        risks: 风险点列表
        strengths: 优势列表
        recommendation: 推荐等级
        summary: 匹配总结
    返回:
        MatchResult: 创建的匹配结果
    """
    match = models.MatchResult(
        job_id=job_id,
        candidate_id=candidate_id,
        total_score=total_score,
        dimension_scores_json=dimension_scores,
        evidence_json=evidence,
        risk_json=risks,
        strengths_json=strengths,
        recommendation=recommendation,
        summary=summary,
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


def get_match_results_by_job(
    db: Session, job_id: str
) -> List[models.MatchResult]:
    """
    获取某个岗位下所有候选人的匹配结果，按分数降序排列。

    参数:
        db: 数据库会话
        job_id: 岗位ID
    返回:
        List[MatchResult]: 按分数从高到低的匹配结果
    """
    return (
        db.query(models.MatchResult)
        .filter(models.MatchResult.job_id == job_id)
        .order_by(models.MatchResult.total_score.desc())
        .all()
    )


def get_match_result(
    db: Session, job_id: str, candidate_id: str
) -> Optional[models.MatchResult]:
    """获取单个候选人对单个岗位的匹配结果。"""
    return (
        db.query(models.MatchResult)
        .filter(
            models.MatchResult.job_id == job_id,
            models.MatchResult.candidate_id == candidate_id,
        )
        .first()
    )
