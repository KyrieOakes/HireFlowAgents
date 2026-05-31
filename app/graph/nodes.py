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
from app.agents.jd_agent import analyze_jd
from app.agents.resume_agent import parse_resume, batch_parse_resumes
from app.agents.match_agent import match_candidate, batch_match_candidates
from app.agents.ranking_agent import rank_candidates
from app.services.rag_service import index_resume, search_evidence_for_match


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

    evidence = {}

    for profile in candidates:
        candidate_id = profile.get("candidate_id", "")

        if not candidate_id:
            continue

        try:
            # 用 JD 要求检索该候选人的简历证据
            results = search_evidence_for_match(
                jd_profile=jd_profile,
                candidate_id=candidate_id,
                top_k=5,
            )
            evidence[candidate_id] = results
        except Exception as e:
            # 检索失败不阻塞流程，该候选人没有证据
            evidence[candidate_id] = []

    return {"retrieved_evidence": evidence}


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
    对所有候选人进行排序。

    按总分从高到低排列，分配推荐等级，生成 shortlist。
    结果写回 state.ranking_results。
    """
    match_results = state.get("match_results", [])

    if not match_results:
        return {"errors": ["没有匹配结果，无法排序"]}

    # 调用 Ranking Agent
    ranking = await rank_candidates(match_results)

    return {"ranking_results": ranking}


# ================================================================
# 7. Human Review 节点 (人工审核)
# ================================================================

async def human_review_node(state: HiringState) -> Dict[str, Any]:
    """
    人工审核节点。

    在此暂停工作流，等待人工确认。
    实际实现中，LangGraph 的 interrupt 会暂停执行。
    """
    return {"human_review_status": "pending"}


# ================================================================
# 8. 错误处理节点
# ================================================================

async def error_handler_node(state: HiringState) -> Dict[str, Any]:
    """
    错误处理节点。

    收集并展示工作流中发生的所有错误。
    """
    errors = state.get("errors", [])
    return {"human_review_status": "error"}
