"""
app/api/matching.py
====================
匹配结果只读 API。

匹配执行统一由 ``POST /workflow/run`` 进入 LangGraph；本模块只负责读取已经
持久化的排名和候选人详细评分，不再保留旧的直连 Agent 编排路由。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import crud
from app.database.session import get_db


router = APIRouter(prefix="/jobs", tags=["matching"])


@router.get("/{job_id}/ranking")
async def get_ranking(
    job_id: str,
    limit: int = 0,
    db: Session = Depends(get_db),
):
    """
    获取已经由 LangGraph 保存的候选人排名。

    参数:
        job_id: 岗位唯一 ID。
        limit: 0 返回全部，正整数只返回前 N 条。
    """
    match_results = crud.get_match_results_by_job(db, job_id)

    if not match_results:
        raise HTTPException(
            status_code=404,
            detail="该岗位还没有匹配结果，请先通过 /workflow/run 启动筛选工作流",
        )

    if limit > 0:
        match_results = match_results[:limit]

    return {
        "job_id": job_id,
        "ranked_candidates": [
            {
                "rank": index + 1,
                "candidate_id": result.candidate_id,
                "total_score": result.total_score,
                "dimension_scores": result.dimension_scores_json,
                "strengths": result.strengths_json,
                "risks": result.risk_json,
                "recommendation": result.recommendation,
                "summary": result.summary,
            }
            for index, result in enumerate(match_results)
        ],
    }


@router.get("/{job_id}/candidates/{candidate_id}/detail")
async def get_match_detail(
    job_id: str,
    candidate_id: str,
    db: Session = Depends(get_db),
):
    """获取单个候选人对当前岗位的维度分、证据、优势和风险。"""
    result = crud.get_match_result(db, job_id, candidate_id)

    if not result:
        raise HTTPException(status_code=404, detail="该候选人对该岗位没有匹配结果")

    return {
        "job_id": job_id,
        "candidate_id": candidate_id,
        "total_score": result.total_score,
        "dimension_scores": result.dimension_scores_json,
        "evidence": result.evidence_json,
        "strengths": result.strengths_json,
        "risks": result.risk_json,
        "recommendation": result.recommendation,
        "summary": result.summary,
    }
