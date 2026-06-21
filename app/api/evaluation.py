"""
app/api/evaluation.py
======================
邮件草稿和评估报告 API。

POST /jobs/{job_id}/candidates/{candidate_id}/email-draft  → 生成邮件草稿
GET  /jobs/{job_id}/candidates/{candidate_id}/email-draft  → 获取草稿列表
POST /email-drafts/{email_id}/approve                       → 批准草稿(不发送)
GET  /evaluation/report                                     → 系统评估报告
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.session import get_db
from app.database import crud
from app.agents.email_agent import generate_email_draft

router = APIRouter(tags=["evaluation"])


# ---- 请求模型 ----

class EmailDraftRequest(BaseModel):
    """邮件草稿生成请求。"""
    email_type: str = "interview_invite"  # interview_invite / rejection / follow_up / next_round


# ---- 邮件草稿 API ----

@router.post("/jobs/{job_id}/candidates/{candidate_id}/email-draft")
async def create_email_draft(
    job_id: str,
    candidate_id: str,
    request: EmailDraftRequest,
    db: Session = Depends(get_db),
):
    """
    生成 HR 邮件草稿。

    支持的 email_type:
    - interview_invite: 面试邀请
    - rejection: 拒信
    - follow_up: 跟进
    - next_round: 下一轮通知

    注意: 只生成草稿, 不发送。需要调用 /email-drafts/{id}/approve 审核。
    """
    valid_types = {"interview_invite", "rejection", "follow_up", "next_round"}
    if request.email_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"无效的邮件类型。支持: {', '.join(valid_types)}",
        )

    job = crud.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在")

    candidate = crud.get_candidate(db, candidate_id)
    if not candidate or not candidate.profile_json:
        raise HTTPException(status_code=404, detail="候选人不存在或尚未解析")

    # 尝试获取面试评价 (可选)
    evaluation = None
    eval_entry = crud.get_interview_evaluation(db, job_id, candidate_id)
    if eval_entry and eval_entry.evaluation_json:
        evaluation = eval_entry.evaluation_json

    # 调用 Email Agent
    try:
        draft = await generate_email_draft(
            candidate_profile=candidate.profile_json,
            job_title=job.title or job.jd_profile_json.get("job_title", "未知岗位") if job.jd_profile_json else "未知岗位",
            email_type=request.email_type,
            evaluation_result=evaluation,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"邮件生成失败: {str(e)}")

    # 保存草稿
    saved = crud.save_email_draft(
        db, job_id, candidate_id,
        email_type=draft["email_type"],
        subject=draft["subject"],
        body=draft["body"],
    )

    return {
        "email_id": saved.email_id,
        "job_id": job_id,
        "candidate_id": candidate_id,
        "email_type": saved.email_type,
        "subject": saved.subject,
        "body": saved.body,
        "status": saved.status,
        "requires_human_approval": True,
        "message": "草稿已生成。请审核后调用 /email-drafts/{email_id}/approve 批准",
    }


@router.get("/jobs/{job_id}/candidates/{candidate_id}/email-draft")
async def get_email_drafts(
    job_id: str,
    candidate_id: str,
    db: Session = Depends(get_db),
):
    """获取候选人的所有邮件草稿。"""
    drafts = crud.get_email_drafts(db, job_id, candidate_id)
    return {
        "job_id": job_id,
        "candidate_id": candidate_id,
        "drafts": [
            {
                "email_id": d.email_id,
                "email_type": d.email_type,
                "subject": d.subject,
                "body": d.body,
                "status": d.status,
            }
            for d in drafts
        ],
    }


@router.post("/email-drafts/{email_id}/approve")
async def approve_email(
    email_id: str,
    db: Session = Depends(get_db),
):
    """
    批准邮件草稿 (只改状态为 approved, 不实际发送)。

    这步是人工审核环节:
    - 审核人确认邮件内容无误后调用
    - 系统只把 status 从 draft 改为 approved
    - 实际发送由 HR 在邮件系统中完成
    """
    draft = crud.approve_email_draft(db, email_id)
    if not draft:
        raise HTTPException(status_code=404, detail="邮件草稿不存在")

    return {
        "email_id": email_id,
        "status": "approved",
        "message": "草稿已批准 (未发送)。请通过邮件系统手动发送。",
    }


# ================================================================
# 系统评估报告 API (已有, Phase 1.1)
# ================================================================

@router.get("/evaluation/report")
async def get_evaluation_report():
    """获取系统评估报告。"""
    return {"status": "ok", "message": "评估报告请运行 evaluation/ 下的 Notebook 或 run_eval.py"}


@router.get("/evaluation/parsing")
async def get_parsing_eval():
    """获取简历解析评估。"""
    return {"status": "ok", "message": "请运行 evaluation/run_parsing_eval.py"}


@router.get("/evaluation/ranking")
async def get_ranking_eval():
    """获取排序评估。"""
    return {"status": "ok", "message": "请运行 evaluation/run_ranking_eval.py"}


@router.get("/evaluation/workflow")
async def get_workflow_eval():
    """获取工作流可靠性评估。"""
    return {"status": "ok", "message": "请运行 evaluation/run_rag_eval.py"}
