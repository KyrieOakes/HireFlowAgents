"""
app/api/interview.py
=====================
面试相关 API: 问题生成 + 面试评价。

POST /jobs/{job_id}/candidates/{candidate_id}/questions      → 生成面试问题
GET  /jobs/{job_id}/candidates/{candidate_id}/questions      → 获取已生成的问题
POST /jobs/{job_id}/candidates/{candidate_id}/evaluate       → 提交面试评价
GET  /jobs/{job_id}/candidates/{candidate_id}/evaluation     → 获取面试评价
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.session import get_db
from app.database import crud
from app.agents.interview_agent import generate_questions
from app.agents.evaluation_agent import evaluate_candidate

router = APIRouter(prefix="/jobs", tags=["interview"])


# ---- 请求模型 ----

class EvaluateRequest(BaseModel):
    """面试评价请求。"""
    interview_feedback: str  # 面试官填写的面试记录/反馈文本


# ---- 面试问题 API ----

@router.post("/{job_id}/candidates/{candidate_id}/questions")
async def create_questions(
    job_id: str,
    candidate_id: str,
    db: Session = Depends(get_db),
):
    """
    为指定候选人生成定制化面试问题。

    步骤:
    1. 查询 job, candidate, match_result
    2. 调用 Interview Agent 生成问题
    3. 保存到 interview_questions 表
    4. 返回问题列表
    """
    # 查询岗位
    job = crud.get_job(db, job_id)
    if not job or not job.jd_profile_json:
        raise HTTPException(status_code=404, detail="岗位不存在或尚未解析")

    # 查询候选人
    candidate = crud.get_candidate(db, candidate_id)
    if not candidate or not candidate.profile_json:
        raise HTTPException(status_code=404, detail="候选人不存在或尚未解析")

    # 查询匹配结果
    match = crud.get_match_result(db, job_id, candidate_id)
    if not match:
        raise HTTPException(status_code=404, detail="请先执行匹配评分")

    # 调用 Interview Agent
    try:
        questions = await generate_questions(
            jd_profile=job.jd_profile_json,
            candidate_profile=candidate.profile_json,
            match_result={
                "risks": match.risk_json or [],
                "total_score": match.total_score,
                "recommendation": match.recommendation,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"面试问题生成失败: {str(e)}")

    # 保存到数据库
    saved = crud.save_interview_questions(db, job_id, candidate_id, questions)

    return {
        "job_id": job_id,
        "candidate_id": candidate_id,
        "questions": [
            {
                "question_id": q.question_id,
                "question_type": q.question_type,
                "question": q.question,
                "purpose": q.purpose,
            }
            for q in saved
        ],
    }


@router.get("/{job_id}/candidates/{candidate_id}/questions")
async def get_questions(
    job_id: str,
    candidate_id: str,
    db: Session = Depends(get_db),
):
    """
    获取已生成的面试问题列表。
    """
    questions = crud.get_interview_questions(db, job_id, candidate_id)
    return {
        "job_id": job_id,
        "candidate_id": candidate_id,
        "questions": [
            {
                "question_id": q.question_id,
                "question_type": q.question_type,
                "question": q.question,
                "purpose": q.purpose,
            }
            for q in questions
        ],
    }


# ---- 面试评价 API ----

@router.post("/{job_id}/candidates/{candidate_id}/evaluate")
async def create_evaluation(
    job_id: str,
    candidate_id: str,
    request: EvaluateRequest,
    db: Session = Depends(get_db),
):
    """
    提交面试反馈, 生成结构化评价。

    步骤:
    1. 查询 job, candidate, match_result
    2. 调用 Evaluation Agent
    3. 保存到 interview_evaluations 表
    4. 返回评价 (requires_human_review 固定为 true)
    """
    job = crud.get_job(db, job_id)
    if not job or not job.jd_profile_json:
        raise HTTPException(status_code=404, detail="岗位不存在或尚未解析")

    candidate = crud.get_candidate(db, candidate_id)
    if not candidate or not candidate.profile_json:
        raise HTTPException(status_code=404, detail="候选人不存在或尚未解析")

    match = crud.get_match_result(db, job_id, candidate_id)
    if not match:
        raise HTTPException(status_code=404, detail="请先执行匹配评分")

    try:
        evaluation = await evaluate_candidate(
            interview_feedback=request.interview_feedback,
            candidate_profile=candidate.profile_json,
            match_result={
                "risks": match.risk_json or [],
                "total_score": match.total_score,
                "recommendation": match.recommendation,
            },
            jd_profile=job.jd_profile_json,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"面试评价生成失败: {str(e)}")

    # 保存
    crud.save_interview_evaluation(
        db, job_id, candidate_id,
        feedback_text=request.interview_feedback,
        evaluation=evaluation,
    )

    return {
        "job_id": job_id,
        "candidate_id": candidate_id,
        "evaluation": evaluation,
    }


@router.get("/{job_id}/candidates/{candidate_id}/evaluation")
async def get_evaluation(
    job_id: str,
    candidate_id: str,
    db: Session = Depends(get_db),
):
    """
    获取面试评价。
    """
    eval_entry = crud.get_interview_evaluation(db, job_id, candidate_id)
    if not eval_entry:
        raise HTTPException(status_code=404, detail="该候选人还没有面试评价")

    return {
        "job_id": job_id,
        "candidate_id": candidate_id,
        "feedback_text": eval_entry.feedback_text,
        "evaluation": eval_entry.evaluation_json,
        "final_recommendation": eval_entry.final_recommendation,
    }
