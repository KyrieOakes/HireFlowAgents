"""
app/agents/ranking_agent.py
============================
Ranking Agent: 候选人排序 Agent。

职责: 根据 Match Agent 的评分结果，对所有候选人进行排序和分级。
这个 Agent 主要使用代码逻辑 (不需要 LLM)，LLM 只用于生成排序解释。

输入: 所有候选人的 match_results 列表
输出: 排序后的结果 + shortlist + 排序解释

推荐等级:
- Strong Match: 总分 >= 80
- Medium Match: 65 <= 总分 < 80
- Weak Match: 50 <= 总分 < 65
- Not Recommended: 总分 < 50
"""

from typing import Dict, Any, List
from app.services.llm_service import call_llm


async def rank_candidates(
    match_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    对所有候选人进行排序和分级。

    这个函数分三步:
    1. 按 total_score 从高到低排序 (纯代码逻辑)
    2. 分配推荐等级 (纯代码逻辑)
    3. 生成排序解释 (调用 LLM)

    参数:
        match_results: Match Agent 输出的所有候选人评分列表
    返回:
        dict: {
            "ranked_candidates": 排序后的候选人列表,
            "shortlist": 推荐进入面试的候选人ID列表,
            "explanation": 排序解释文字,
            "summary": 各等级人数统计
        }
    """
    # ================================================================
    # 第1步: 按分数排序
    # ================================================================
    # sorted() 函数: 对列表排序
    # key=lambda x: x["total_score"]: 按每个结果的 total_score 字段排序
    # reverse=True: 从高到低 (默认是从低到高)
    ranked = sorted(
        match_results,
        key=lambda x: x.get("total_score", 0),
        reverse=True,
    )

    # ================================================================
    # 第2步: 分配推荐等级 + 生成 shortlist
    # ================================================================
    # 遍历排序后的结果，为每个候选人标注等级
    shortlist = []  # 推荐进入面试的候选人ID列表

    for result in ranked:
        score = result.get("total_score", 0)

        # 根据分数区间分配等级
        if score >= 80:
            level = "Strong Match"
            # 80分以上自动进入 shortlist
            shortlist.append(result.get("candidate_id", ""))
        elif score >= 65:
            level = "Medium Match"
            # 65-79分的候选人也加入 shortlist (可以进面试)
            shortlist.append(result.get("candidate_id", ""))
        elif score >= 50:
            level = "Weak Match"
            # 50-64分: 备选，不自动进入 shortlist
        else:
            level = "Not Recommended"

        # 把等级写回结果中
        result["recommendation"] = level

    # ================================================================
    # 第3步: 生成排序解释
    # ================================================================
    # 统计各级别人数
    strong_count = sum(1 for r in ranked if r.get("recommendation") == "Strong Match")
    medium_count = sum(1 for r in ranked if r.get("recommendation") == "Medium Match")
    weak_count = sum(1 for r in ranked if r.get("recommendation") == "Weak Match")
    not_rec_count = sum(1 for r in ranked if r.get("recommendation") == "Not Recommended")

    # 调用 LLM 生成排序解释
    explanation = await _generate_explanation(
        ranked_candidates=ranked,
        shortlist=shortlist,
        stats={
            "total": len(ranked),
            "strong": strong_count,
            "medium": medium_count,
            "weak": weak_count,
            "not_recommended": not_rec_count,
        },
    )

    # ================================================================
    # 组装返回结果
    # ================================================================
    return {
        "ranked_candidates": ranked,
        "shortlist": shortlist,
        "explanation": explanation,
        "summary": {
            "total_candidates": len(ranked),
            "strong_match": strong_count,
            "medium_match": medium_count,
            "weak_match": weak_count,
            "not_recommended": not_rec_count,
        },
    }


async def _generate_explanation(
    ranked_candidates: List[Dict[str, Any]],
    shortlist: List[str],
    stats: Dict[str, int],
) -> str:
    """
    让 LLM 生成排序解释。

    解释为什么这样排名，帮助 HR 理解排序结果。

    参数:
        ranked_candidates: 排序后的候选人列表
        shortlist: shortlist 名单
        stats: 统计数据
    返回:
        str: LLM 生成的中文解释
    """
    # 构建简要的候选人排名表格
    rank_table = ""
    for i, candidate in enumerate(ranked_candidates):
        rank_table += (
            f"  第{i+1}名: {candidate.get('candidate_id', '?')} "
            f"- 总分{candidate.get('total_score', 0):.0f} "
            f"- {candidate.get('recommendation', '')}\n"
        )

    system_prompt = "你是一位资深的招聘顾问。请用中文简要解释候选人排序结果。"
    user_message = f"""以下是针对某岗位的候选人排序结果:

{rank_table}

统计:
- 总候选人数: {stats['total']}
- Strong Match: {stats['strong']}人
- Medium Match: {stats['medium']}人
- Weak Match: {stats['weak']}人
- Not Recommended: {stats['not_recommended']}人

Shortlist (推荐进入面试): {len(shortlist)}人

请用2-3句话简要解释:
1. 排名靠前的候选人为什么排在前列
2. 对招聘决策的建议"""

    # 调用 LLM (自由文本，不需要结构化)
    explanation = call_llm(
        system_prompt=system_prompt,
        user_message=user_message,
    )

    return explanation
