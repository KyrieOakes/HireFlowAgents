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
from app.services.pre_screening import pre_screen_candidates

router = APIRouter(prefix="/jobs", tags=["matching"])


@router.post("/{job_id}/match")
async def run_matching(
    job_id: str,
    limit: int = 0,
    db: Session = Depends(get_db),
):
    """
    两阶段匹配 + 排序:
      Stage 1 (粗筛): 关键词匹配, 零LLM调用, 筛选出 top_k
      Stage 2 (精排): LLM 多维度评分, 仅对粗筛结果

    参数:
        limit: 最终展示多少候选人 (0=全部)
    步骤:
    1. 粗筛: 从全部候选人中快速筛选 top_candidates
    2. 精排: LLM 对粗筛结果进行详细评分
    3. 排序 + 生成 shortlist
    4. 保存结果到数据库
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
    all_candidates = []
    for c in parsed_candidates:
        profile = c.profile_json.copy()
        profile["candidate_id"] = c.candidate_id
        all_candidates.append(profile)

    total_in_db = len(all_candidates)

    # JD profile (后续多次使用)
    jd_profile = job.jd_profile_json

    # ---- Stage 1: 粗筛 (关键词匹配, 零LLM调用) ----
    # 粗筛池大小: limit * 3, 最少15个, 最多不超过全部
    pool_size = max(limit * 3, 15) if limit and limit > 0 else len(all_candidates)
    pool_size = min(pool_size, len(all_candidates))

    candidate_profiles = pre_screen_candidates(
        jd_profile=jd_profile,
        candidates=all_candidates,
        top_k=pool_size,
    )

    prescreened_count = len(candidate_profiles)

    # ---- Stage 2: 精排 (LLM 多维度评分) ----
    # 对粗筛后的候选人进行 LLM 评分
    # 如果有限制, 最终只保留 limit 个
    if limit and limit > 0:
        candidate_profiles = candidate_profiles[:limit]

    matched_count = len(candidate_profiles)

    # Step 3: 匹配评分
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
        "total_in_db": total_in_db,
        "prescreened": prescreened_count,
        "llm_scored": matched_count,
        "limit": limit if limit > 0 else None,
        "ranking": ranking,
        "match_results": match_results,
    }


@router.get("/{job_id}/ranking")
async def get_ranking(
    job_id: str,
    limit: int = 0,
    db: Session = Depends(get_db),
):
    """
    获取候选人排名结果 (支持limit限制)。

    从数据库中读取之前保存的匹配评分，按分数排序返回。
    参数: limit=0 返回全部, limit>0 只返回前N条。
    """
    match_results = crud.get_match_results_by_job(db, job_id)

    if not match_results:
        raise HTTPException(status_code=404, detail="该岗位还没有匹配结果，请先调用 /jobs/{job_id}/match")

    # 应用 limit
    if limit and limit > 0:
        match_results = match_results[:limit]

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
