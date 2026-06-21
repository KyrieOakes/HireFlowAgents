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
        # 更新名字逻辑:
        # - 如果原名是"申请人*"(系统自动生成)且LLM提取到了真实姓名 → 更新
        # - 如果原名是"申请人*"但LLM没提取到 → 保持自动命名
        # - 如果原名不是自动生成的 → 保持原样(用户手动填的)
        is_auto_named = candidate.name and candidate.name.startswith("申请人")
        new_name = profile.get("name", "")
        # LLM提取的名字是否看起来像真实人名 (不是空, 不是申请人模式)
        is_real_name = bool(new_name) and not new_name.startswith("申请人")
        if is_auto_named and is_real_name:
            candidate.name = new_name
        # 如果用户上传时手动填写了姓名，就尊重用户输入，不用解析结果覆盖。
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


# ============================================================
# 删除操作
# ============================================================

def delete_job(db: Session, job_id: str) -> bool:
    """
    删除岗位及其关联的所有记录。
    """
    job = get_job(db, job_id)
    if not job:
        return False
    # 手动清理 interview/evaluation/email 表 (job_id 外键)
    db.query(models.InterviewQuestion).filter(
        models.InterviewQuestion.job_id == job_id
    ).delete()
    db.query(models.InterviewEvaluation).filter(
        models.InterviewEvaluation.job_id == job_id
    ).delete()
    db.query(models.EmailDraft).filter(
        models.EmailDraft.job_id == job_id
    ).delete()
    db.delete(job)
    db.commit()
    return True


def delete_candidate(db: Session, candidate_id: str) -> bool:
    """
    删除候选人及其关联的所有记录。

    先手动清理子表 (面试/评价/邮件), 再删候选人。
    SQLAlchemy cascade 只对已配置 relationship 的表生效,
    新增的 interview_questions 等表需要显式删除。
    """
    candidate = get_candidate(db, candidate_id)
    if not candidate:
        return False
    # 手动清理关联表 (这些表没有在 Candidate model 中配置 relationship+cascade)
    db.query(models.InterviewQuestion).filter(
        models.InterviewQuestion.candidate_id == candidate_id
    ).delete()
    db.query(models.InterviewEvaluation).filter(
        models.InterviewEvaluation.candidate_id == candidate_id
    ).delete()
    db.query(models.EmailDraft).filter(
        models.EmailDraft.candidate_id == candidate_id
    ).delete()
    db.delete(candidate)
    db.commit()
    return True


# ============================================================
# 面试问题 (InterviewQuestion) CRUD
# ============================================================

def save_interview_questions(
    db: Session,
    job_id: str,
    candidate_id: str,
    questions: list,
) -> List[models.InterviewQuestion]:
    """
    保存候选人的面试问题列表。

    先删除该候选人之前的问题, 再批量插入新的。
    这样每次生成都是全新的问题集, 不会累积。

    参数:
        db: 数据库会话
        job_id: 岗位ID
        candidate_id: 候选人ID
        questions: 问题列表, 每个元素含 question_type, question, purpose
    返回:
        List[InterviewQuestion]: 保存的问题对象
    """
    # 先删除旧问题 (如果重新生成)
    db.query(models.InterviewQuestion).filter(
        models.InterviewQuestion.job_id == job_id,
        models.InterviewQuestion.candidate_id == candidate_id,
    ).delete()

    # 批量插入新问题
    db_questions = []
    for q in questions:
        entry = models.InterviewQuestion(
            job_id=job_id,
            candidate_id=candidate_id,
            question_type=q.get("question_type", ""),
            question=q.get("question", ""),
            purpose=q.get("purpose", ""),
        )
        db.add(entry)
        db_questions.append(entry)

    db.commit()
    return db_questions


def get_interview_questions(
    db: Session,
    job_id: str,
    candidate_id: str,
) -> List[models.InterviewQuestion]:
    """获取某个候选人针对某个岗位的面试问题。"""
    return (
        db.query(models.InterviewQuestion)
        .filter(
            models.InterviewQuestion.job_id == job_id,
            models.InterviewQuestion.candidate_id == candidate_id,
        )
        .order_by(models.InterviewQuestion.created_at)
        .all()
    )


# ============================================================
# 面试评价 (InterviewEvaluation) CRUD
# ============================================================

def save_interview_evaluation(
    db: Session,
    job_id: str,
    candidate_id: str,
    feedback_text: str,
    evaluation: dict,
) -> models.InterviewEvaluation:
    """
    保存候选人面试评价。

    如果已有评价则更新, 否则新建。
    评价包含面试官的原始反馈 + Evaluation Agent 的结构化评价。

    参数:
        db: 数据库会话
        job_id: 岗位ID
        candidate_id: 候选人ID
        feedback_text: 面试官填写的原始反馈
        evaluation: Evaluation Agent 生成的结构化评价
    返回:
        InterviewEvaluation: 保存的评价对象
    """
    # 查找是否已有评价
    existing = (
        db.query(models.InterviewEvaluation)
        .filter(
            models.InterviewEvaluation.job_id == job_id,
            models.InterviewEvaluation.candidate_id == candidate_id,
        )
        .first()
    )

    if existing:
        existing.feedback_text = feedback_text
        existing.evaluation_json = evaluation
        existing.final_recommendation = evaluation.get("recommendation", "")
        db.commit()
        db.refresh(existing)
        return existing
    else:
        entry = models.InterviewEvaluation(
            job_id=job_id,
            candidate_id=candidate_id,
            feedback_text=feedback_text,
            evaluation_json=evaluation,
            final_recommendation=evaluation.get("recommendation", ""),
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry


def get_interview_evaluation(
    db: Session,
    job_id: str,
    candidate_id: str,
) -> models.InterviewEvaluation | None:
    """获取某个候选人的面试评价。"""
    return (
        db.query(models.InterviewEvaluation)
        .filter(
            models.InterviewEvaluation.job_id == job_id,
            models.InterviewEvaluation.candidate_id == candidate_id,
        )
        .first()
    )


# ============================================================
# 邮件草稿 (EmailDraft) CRUD
# ============================================================

def save_email_draft(
    db: Session,
    job_id: str,
    candidate_id: str,
    email_type: str,
    subject: str,
    body: str,
) -> models.EmailDraft:
    """
    保存 HR 邮件草稿。

    每次生成新草稿时会覆盖同一候选人的同类型旧草稿。
    状态固定为 "draft", 需要人工审核后改为 "approved"。

    参数:
        db: 数据库会话
        job_id: 岗位ID
        candidate_id: 候选人ID
        email_type: 邮件类型 (interview_invite/rejection/follow_up/next_round)
        subject: 邮件标题
        body: 邮件正文
    返回:
        EmailDraft: 保存的草稿对象
    """
    # 删除同一候选人的同类型旧草稿
    db.query(models.EmailDraft).filter(
        models.EmailDraft.job_id == job_id,
        models.EmailDraft.candidate_id == candidate_id,
        models.EmailDraft.email_type == email_type,
    ).delete()

    draft = models.EmailDraft(
        job_id=job_id,
        candidate_id=candidate_id,
        email_type=email_type,
        subject=subject,
        body=body,
        status="draft",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def get_email_drafts(
    db: Session,
    job_id: str,
    candidate_id: str,
) -> List[models.EmailDraft]:
    """获取某个候选人的所有邮件草稿。"""
    return (
        db.query(models.EmailDraft)
        .filter(
            models.EmailDraft.job_id == job_id,
            models.EmailDraft.candidate_id == candidate_id,
        )
        .order_by(models.EmailDraft.created_at.desc())
        .all()
    )


def approve_email_draft(
    db: Session,
    email_id: str,
) -> models.EmailDraft | None:
    """
    批准邮件草稿 (只改状态, 不发送)。

    参数:
        db: 数据库会话
        email_id: 邮件草稿ID
    返回:
        EmailDraft 或 None
    """
    draft = db.query(models.EmailDraft).filter(
        models.EmailDraft.email_id == email_id
    ).first()
    if draft:
        draft.status = "approved"
        db.commit()
        db.refresh(draft)
    return draft
