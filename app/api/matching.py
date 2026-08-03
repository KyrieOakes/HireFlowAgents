"""
app/api/matching.py
====================
候选人匹配与排序 API。

POST /jobs/{job_id}/match     → 执行匹配 + 排序
GET  /jobs/{job_id}/ranking   → 获取排序结果
GET  /jobs/{job_id}/candidates/{id}/detail → 获取单个候选人的详细评分
"""

import asyncio
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.evidence_agent import batch_collect_evidence, build_interventions
from app.database.session import get_db
from app.database import crud
from app.agents.match_agent import batch_match_candidates
from app.agents.ranking_agent import rank_candidates
from app.services.pre_screening import pre_screen_candidates
from app.services.rag_service import ensure_resume_indexed

router = APIRouter(prefix="/jobs", tags=["matching"])


async def _ensure_candidate_indexes(
    candidate_profiles: list[dict],
    candidate_records: dict[str, object],
    db: Session,
) -> int:
    """匹配前检查候选人 Qdrant 索引，并自动重建缺失项。"""
    from app.services.document_loader import chunk_documents
    from langchain_core.documents import Document

    rebuilt_count = 0
    failed_names: list[str] = []

    for profile in candidate_profiles:
        candidate_id = str(profile.get("candidate_id", ""))
        candidate = candidate_records.get(candidate_id)
        if not candidate:
            failed_names.append(candidate_id or "未知候选人")
            continue

        try:
            point_ids = await asyncio.to_thread(
                ensure_resume_indexed,
                candidate.resume_text,
                candidate_id,
            )
            if point_ids is None:
                continue

            # 自动重建成功后同步替换 PostgreSQL 中的派生 chunk 映射。
            document = Document(
                page_content=candidate.resume_text,
                metadata={"source": "matching_auto_rebuild"},
            )
            chunks = chunk_documents([document])
            crud.save_resume_chunks(
                db,
                candidate_id,
                chunks,
                point_ids,
                replace_existing=True,
            )
            rebuilt_count += 1
        except Exception:
            # 不把底层地址或认证信息拼到批量响应中，只返回可操作的服务检查建议。
            failed_names.append(str(profile.get("name") or candidate_id))

    if failed_names:
        names = "、".join(failed_names[:5])
        suffix = "等" if len(failed_names) > 5 else ""
        raise HTTPException(
            status_code=503,
            detail=(
                f"以下候选人的简历证据索引不可用：{names}{suffix}。"
                "请确认 Qdrant 已启动，并在 LM Studio 中加载 Embedding 模型后重试匹配。"
            ),
        )

    return rebuilt_count


@router.post("/{job_id}/match")
async def run_matching(
    job_id: str,
    limit: int = 0,
    agent_failure_action: Literal[
        "ask_user",
        "continue_with_warning",
        "skip_failed",
    ] = "ask_user",
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
    2. ReAct Evidence Agent: 动态调用 Qdrant 工具收集证据
    3. 精排: LLM 对粗筛结果进行详细评分
    4. 排序 + 生成 shortlist
    5. 保存结果到数据库

    agent_failure_action 控制工具错误耗尽后的行为:
    - ask_user: 暂停评分并把可选操作返回前端
    - continue_with_warning: 使用已有证据继续，失败候选人标记人工复核
    - skip_failed: 跳过 Agent 技术失败的候选人
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

    # 旧代码会静默吞掉简历索引异常，导致所有候选人被误标为“证据不足”。
    # 这里在调用 Agent 前检查并自动重建，使真实索引故障不会污染招聘判断。
    candidate_records = {candidate.candidate_id: candidate for candidate in parsed_candidates}
    await _ensure_candidate_indexes(candidate_profiles, candidate_records, db)

    # Step 3: 运行受控 ReAct Evidence Agent。
    # Agent 会通过原生 Tool Calling 动态搜索 Qdrant，并返回完整审计轨迹。
    evidence_by_candidate, agent_run_models = await batch_collect_evidence(
        jd_profile=jd_profile,
        candidate_profiles=candidate_profiles,
    )
    agent_runs = [run.model_dump() for run in agent_run_models]
    intervention_models = build_interventions(agent_run_models)
    interventions = [item.model_dump() for item in intervention_models]

    # 默认策略是把不可自动恢复的工具错误交给用户选择，而不是静默当成“无证据”。
    if interventions and agent_failure_action == "ask_user":
        return {
            "status": "needs_human_review",
            "message": "证据 Agent 遇到不可自动恢复的错误，请选择后续操作",
            "job_id": job_id,
            "total_in_db": total_in_db,
            "prescreened": prescreened_count,
            "llm_scored": 0,
            "limit": limit if limit > 0 else None,
            "ranking": {"ranked_candidates": [], "shortlist": []},
            "match_results": [],
            "agent_runs": agent_runs,
            "interventions": interventions,
        }

    if interventions and agent_failure_action == "skip_failed":
        # 只跳过技术失败的候选人；正常完成但证据不足的候选人仍可进入人工复核。
        failed_ids = {item.candidate_id for item in intervention_models}
        candidate_profiles = [
            profile
            for profile in candidate_profiles
            if profile.get("candidate_id") not in failed_ids
        ]

    if not candidate_profiles:
        return {
            "status": "needs_human_review",
            "message": "所有候选人的证据 Agent 都失败或被跳过，无法继续评分",
            "job_id": job_id,
            "total_in_db": total_in_db,
            "prescreened": prescreened_count,
            "llm_scored": 0,
            "limit": limit if limit > 0 else None,
            "ranking": {"ranked_candidates": [], "shortlist": []},
            "match_results": [],
            "agent_runs": agent_runs,
            "interventions": interventions,
        }

    # 经过人工选择“继续”时，失败候选人的 evidence 可能为空；Match Agent 必须
    # 明确把它当作证据缺失，而不是把系统故障解释成候选人能力不足。
    matched_count = len(candidate_profiles)

    # Step 4: 匹配评分 (传入 RAG 证据)
    rubric = job.rubric_json or jd_profile.get("rubric")

    match_results = await batch_match_candidates(
        jd_profile=jd_profile,
        candidate_profiles=candidate_profiles,
        evidence_by_candidate=evidence_by_candidate,
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
        "status": "completed",
        "message": "证据 Agent、匹配评分和排序已完成",
        "job_id": job_id,
        "total_in_db": total_in_db,
        "prescreened": prescreened_count,
        "llm_scored": matched_count,
        "limit": limit if limit > 0 else None,
        "ranking": ranking,
        "match_results": match_results,
        "agent_runs": agent_runs,
        "interventions": interventions,
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
