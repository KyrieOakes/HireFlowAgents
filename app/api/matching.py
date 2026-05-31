"""
app/api/matching.py
====================
候选人匹配与排序 API。

POST /jobs/{job_id}/match     → 执行匹配 + 排序
GET  /jobs/{job_id}/ranking   → 获取排序结果
GET  /jobs/{job_id}/candidates/{id}/detail → 获取单个候选人的详细评分
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database import crud
from app.agents.match_agent import batch_match_candidates
from app.agents.ranking_agent import rank_candidates

router = APIRouter(prefix="/jobs", tags=["matching"])


@router.post("/{job_id}/match")
async def run_matching(job_id: str, db: Session = Depends(get_db)):
    """
    执行候选人匹配 + 排序。

    这是核心 API 端点，调用 Match Agent 和 Ranking Agent。
    步骤:
    1. 获取岗位的 JD profile
    2. 获取所有候选人 profile
    3. 批量匹配评分
    4. 排序 + 生成 shortlist
    5. 保存结果到数据库
    """
    # Step 1: 获取岗位
    job = crud.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在")
    if not job.jd_profile_json:
        raise HTTPException(status_code=400, detail="岗位尚未解析，请先调用 /jobs/{job_id}/parse")

    # Step 2: 获取所有候选人
    candidates = crud.get_all_candidates(db)
    if not candidates:
        raise HTTPException(status_code=400, detail="没有候选人，请先上传简历")

    # 过滤出已解析的候选人
    parsed_candidates = [c for c in candidates if c.profile_json]
    if not parsed_candidates:
        raise HTTPException(status_code=400, detail="没有已解析的候选人，请先解析简历")

    # 构建候选人画像列表
    candidate_profiles = []
    for c in parsed_candidates:
        profile = c.profile_json.copy()
        profile["candidate_id"] = c.candidate_id
        candidate_profiles.append(profile)

    # Step 3: 匹配评分
    jd_profile = job.jd_profile_json
    rubric = job.rubric_json or jd_profile.get("rubric")

    match_results = await batch_match_candidates(
        jd_profile=jd_profile,
        candidate_profiles=candidate_profiles,
        rubric=rubric,
    )

    # Step 4: 排序
    ranking = await rank_candidates(match_results)

    # Step 5: 保存匹配结果到数据库
    for result in match_results:
        crud.save_match_result(
            db=db,
            job_id=job_id,
            candidate_id=result.get("candidate_id", ""),
            total_score=result.get("total_score", 0),
            dimension_scores=result.get("dimension_scores", {}).model_dump()
            if hasattr(result.get("dimension_scores", {}), "model_dump")
            else result.get("dimension_scores", {}),
            evidence=result.get("evidence", []),
            risks=result.get("risks", []),
            strengths=result.get("strengths", []),
            recommendation=result.get("recommendation", ""),
            summary=result.get("summary", ""),
        )

    return {
        "job_id": job_id,
        "candidates_matched": len(match_results),
        "ranking": ranking,
        "match_results": match_results,
    }


@router.get("/{job_id}/ranking")
async def get_ranking(job_id: str, db: Session = Depends(get_db)):
    """
    获取候选人排名结果。

    从数据库中读取之前保存的匹配评分，按分数排序返回。
    """
    match_results = crud.get_match_results_by_job(db, job_id)

    if not match_results:
        raise HTTPException(status_code=404, detail="该岗位还没有匹配结果，请先调用 /jobs/{job_id}/match")

    return {
        "job_id": job_id,
        "ranked_candidates": [
            {
                "rank": i + 1,
                "candidate_id": r.candidate_id,
                "total_score": r.total_score,
                "dimension_scores": r.dimension_scores_json,
                "strengths": r.strengths_json,
                "risks": r.risk_json,
                "recommendation": r.recommendation,
                "summary": r.summary,
            }
            for i, r in enumerate(match_results)
        ],
    }


@router.get("/{job_id}/candidates/{candidate_id}/detail")
async def get_match_detail(
    job_id: str,
    candidate_id: str,
    db: Session = Depends(get_db),
):
    """
    获取单个候选人的详细匹配评分。

    包含各维度具体分数、支撑证据和风险分析。
    """
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
