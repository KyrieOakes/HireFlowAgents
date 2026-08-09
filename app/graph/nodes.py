"""
app/graph/nodes.py
==================
LangGraph 工作流节点实现。

每个节点对应招聘流程中的一个步骤。
节点从共享 state 中读取输入，处理后返回更新的字段。
LangGraph 自动将返回的字典合并到全局状态。

节点执行顺序:
  jd_agent → resume_agent → resume_validation → evidence_retrieval
  → match_agent → ranking_agent → human_review
"""

from typing import Dict, Any
from app.graph.state import HiringState
from app.agents.evidence_agent import batch_collect_evidence, build_interventions
from app.agents.jd_agent import analyze_jd
from app.agents.resume_agent import parse_resume, batch_parse_resumes
from app.agents.match_agent import match_candidate, batch_match_candidates
from app.agents.ranking_agent import rank_candidates


# ================================================================
# 1. JD Agent 节点
# ================================================================

async def jd_agent_node(state: HiringState) -> Dict[str, Any]:
    """
    解析岗位描述，提取结构化信息。

    从 state 中读取原始 JD 文本，
    调用 JD Agent 解析为结构化数据，
    结果写回 state.jd_profile。
    """
    # 主流程会优先把数据库中已经解析好的 JD 画像放入 state。
    # 有现成画像时直接复用，可以避免用户每次匹配都再次调用 LLM。
    if state.get("jd_profile"):
        return {}

    jd_text = state.get("jd_text", "")

    if not jd_text:
        return {"errors": ["岗位描述文本为空"]}

    try:
        # 调用 JD Agent 分析
        jd_profile = await analyze_jd(jd_text)
        return {"jd_profile": jd_profile}
    except Exception as e:
        # 如果解析失败，记录错误
        return {"errors": [f"JD 解析失败: {str(e)}"]}


# ================================================================
# 2. Resume Agent 节点
# ================================================================

async def resume_agent_node(state: HiringState) -> Dict[str, Any]:
    """
    解析所有候选人简历。

    从 state 中读取简历文本列表 (resume_texts)，
    逐份调用 Resume Agent 解析为结构化画像，
    结果写回 state.candidate_profiles。

    state 中的 resume_texts 格式:
      [{"candidate_id": "xxx", "text": "简历全文...", "filename": "xxx.pdf"}, ...]
    """
    # 与 JD 节点相同，数据库里已有结构化候选人画像时直接复用。
    # 只有旧的“传入原始简历文本”调用方式才需要在工作流里重新解析。
    if state.get("candidate_profiles"):
        return {}

    resume_texts = state.get("resume_texts", [])

    if not resume_texts:
        return {"errors": ["没有上传任何简历"]}

    candidate_profiles = []

    for resume_entry in resume_texts:
        candidate_id = resume_entry.get("candidate_id", "unknown")
        text = resume_entry.get("text", "")

        if not text:
            continue

        try:
            # 调用 Resume Agent 解析
            profile = await parse_resume(
                resume_text=text,
                candidate_id=candidate_id,
            )
            candidate_profiles.append(profile)
        except Exception as e:
            return {"errors": [f"简历解析失败 ({candidate_id}): {str(e)}"]}

    return {"candidate_profiles": candidate_profiles}


# ================================================================
# 3. Resume Validation 节点
# ================================================================

async def resume_validation_node(state: HiringState) -> Dict[str, Any]:
    """
    检查简历解析是否成功。

    验证每份简历的解析结果是否完整:
    - candidate_profiles 不能为空
    - 每个 profile 至少要能提取出姓名或技能

    如果全部失败，返回错误，流程进入 error_handler。
    如果部分失败，记录警告但继续。
    """
    profiles = state.get("candidate_profiles", [])

    if not profiles:
        return {"errors": ["所有简历解析均失败，无法继续"]}

    # 检查是否有完全空白的解析结果
    empty_profiles = [
        p.get("candidate_id", "?")
        for p in profiles
        if not p.get("name") and not p.get("skills")
    ]

    if len(empty_profiles) == len(profiles):
        return {"errors": [f"所有简历({len(profiles)}份)解析后均为空"]}

    # 部分失败也继续 (后续 Match Agent 会给低分)
    return {}


# ================================================================
# 4. Evidence Retrieval 节点
# ================================================================

async def evidence_retrieval_node(state: HiringState) -> Dict[str, Any]:
    """
    RAG 证据检索节点。

    对每个候选人，用 JD 的关键要求检索简历中相关的文本片段。
    检索结果写回 state.retrieved_evidence。

    state.retrieved_evidence 结构:
      {"candidate_id_1": [{"text": "...", "score": 0.95, "metadata": {...}}, ...],
       "candidate_id_2": [...]}
    """
    jd_profile = state.get("jd_profile", {})
    candidates = state.get("candidate_profiles", [])

    if not jd_profile:
        return {"errors": ["JD profile 为空，无法检索证据"]}

    # 每个候选人运行一个有边界的 ReAct 子图；模型决定查询，工具节点负责
    # 候选人隔离、错误分类、指数退避和审计记录。
    evidence, run_models = await batch_collect_evidence(
        jd_profile=jd_profile,
        candidate_profiles=candidates,
    )
    intervention_models = build_interventions(run_models)

    return {
        "retrieved_evidence": evidence,
        "evidence_agent_runs": [run.model_dump() for run in run_models],
        "evidence_interventions": [item.model_dump() for item in intervention_models],
        # 重试后成功时清空之前的证据审核状态，让条件路由重新判断本轮结果。
        "evidence_review_status": "",
    }


# ================================================================
# 4.1 Evidence Agent 人工介入节点
# ================================================================

async def evidence_intervention_node(state: HiringState) -> Dict[str, Any]:
    """
    Tool Calling 无法自动恢复时暂停工作流，让用户选择继续方式。

    输入是 Agent 的结构化错误列表，输出是 retry/continue/skip/abort 状态；
    PostgresSaver 会保存中断点，服务重启后仍可继续。
    """
    from langgraph.types import interrupt

    interventions = state.get("evidence_interventions", [])
    decision = interrupt(
        {
            "status": "evidence_agent_needs_review",
            "message": "证据 Agent 的自动重试已耗尽，请选择后续操作",
            "interventions": interventions,
            "available_actions": [
                "retry_agent",
                "continue_with_warning",
                "skip_failed",
                "abort",
            ],
        }
    )
    action = decision.get("action", "abort")

    if action == "retry_agent":
        return {"evidence_review_status": "retry"}

    if action == "continue_with_warning":
        return {"evidence_review_status": "continue"}

    if action == "skip_failed":
        failed_ids = {
            item.get("candidate_id")
            for item in interventions
            if item.get("candidate_id")
        }
        remaining_profiles = [
            profile
            for profile in state.get("candidate_profiles", [])
            if profile.get("candidate_id") not in failed_ids
        ]
        if remaining_profiles:
            return {
                "candidate_profiles": remaining_profiles,
                "evidence_review_status": "continue",
            }
        return {
            "evidence_review_status": "abort",
            "errors": state.get("errors", []) + ["所有证据 Agent 失败候选人均被跳过"],
        }

    return {
        "evidence_review_status": "abort",
        "errors": state.get("errors", []) + ["用户终止了证据 Agent 工作流"],
    }


# ================================================================
# 5. Match Agent 节点
# ================================================================

async def match_agent_node(state: HiringState) -> Dict[str, Any]:
    """
    对每个候选人进行匹配评分。

    遍历所有候选人画像，与 JD 要求对比评分。
    评分结果写回 state.match_results。
    """
    jd_profile = state.get("jd_profile", {})
    candidates = state.get("candidate_profiles", [])
    evidence_by_candidate = state.get("retrieved_evidence", {})
    rubric = jd_profile.get("rubric", {})

    if not jd_profile or not candidates:
        return {"errors": ["JD profile 或候选人列表为空，无法匹配"]}

    # 批量匹配评分
    match_results = await batch_match_candidates(
        jd_profile=jd_profile,
        candidate_profiles=candidates,
        evidence_by_candidate=evidence_by_candidate,
        rubric=rubric,
    )

    return {"match_results": match_results}


# ================================================================
# 6. Ranking Agent 节点
# ================================================================

async def ranking_agent_node(state: HiringState) -> Dict[str, Any]:
    """
    对召回池中的所有候选人进行排序，并在精排完成后截取 Top-N。

    按总分从高到低排列，分配推荐等级，生成 shortlist。
    结果写回 state.ranking_results。
    """
    match_results = state.get("match_results", [])
    requested_limit = state.get("requested_limit", 0)

    if not match_results:
        return {"errors": ["没有匹配结果，无法排序"]}

    # Match Agent 已经对整个粗排召回池完成 LLM 评分。
    # Top-N 必须在这些分数全部产生后再截取，才能构成真正的“召回 + 精排”。
    ranking = await rank_candidates(match_results, limit=requested_limit)

    return {"ranking_results": ranking}


# ================================================================
# 7. Human Review 节点 (真实 interrupt)
# ================================================================

async def human_review_node(state: HiringState) -> Dict[str, Any]:
    """
    人工审核节点 — 使用 LangGraph interrupt() 暂停工作流。

    流程暂停后, 前端/API 可以调用 resume 继续:
    - approve:  确认 shortlist, 进入面试流程
    - reject:   驳回, 要求重新匹配
    - modify:   手动调整候选人顺序

    interrupt 是 LangGraph 原生机制, 配合 PostgresSaver:
    - 状态持久化到 PostgreSQL checkpoint
    - 即使服务器重启, 审核状态也能恢复
    - 支持跨天审核 (面试流程可能跨多天)
    """
    from langgraph.types import interrupt

    # 构建审核信息
    ranking = state.get("ranking_results", {})
    ranked = ranking.get("ranked_candidates", [])
    shortlist = ranking.get("shortlist", [])

    review_payload = {
        "status": "pending_review",
        "message": "请审核候选人排序结果, 选择进入面试的候选人",
        "total_candidates": len(ranked),
        "shortlist": shortlist,
        "candidates": [
            {
                "rank": i + 1,
                "candidate_id": c.get("candidate_id", "?"),
                "score": c.get("total_score", 0),
                "recommendation": c.get("recommendation", ""),
            }
            for i, c in enumerate(ranked)
        ],
        "available_actions": ["approve_shortlist", "reject", "modify"],
    }

    # 暂停! 等待人工输入
    # interrupt() 会序列化当前 state 到 PostgresSaver
    # 直到外部调用 resume 才会继续
    human_decision = interrupt(review_payload)

    # 处理人工决策
    action = human_decision.get("action", "reject")
    selected_ids = human_decision.get("selected_candidate_ids", shortlist)

    if action == "approve_shortlist":
        return {
            "human_review_status": "approved",
            "selected_candidate_ids": selected_ids,
        }
    elif action == "modify":
        return {
            "human_review_status": "modified",
            "selected_candidate_ids": human_decision.get("selected_candidate_ids", shortlist),
        }
    else:  # reject
        # “驳回并重新评分”是正常的人工作流动作，不是系统错误。
        # 如果写入 errors，后续即使审核通过，页面仍会误报旧错误。
        return {
            "human_review_status": "rejected",
            "selected_candidate_ids": [],
        }


# ================================================================
# 8. 错误处理节点
# ================================================================

async def error_handler_node(state: HiringState) -> Dict[str, Any]:
    """
    错误处理节点。

    收集并展示工作流中发生的所有错误, 不阻塞流程。
    """
    errors = state.get("errors", [])
    return {"human_review_status": "error", "errors": errors}
