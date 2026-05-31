"""
app/agents/ranking_agent.py
============================
Ranking Agent: 候选人排序 Agent。

职责: 根据 Match Agent 的评分结果，对所有候选人进行排序和分级。
不修改分数，只负责排列和解释。

输入: 所有候选人的 match_results
输出: 排序后的候选人列表 (state.ranking_results)
"""

from typing import Dict, Any, List


async def rank_candidates(
    match_results: List[Dict[str, Any]],
    llm_service,
) -> Dict[str, Any]:
    """
    对所有候选人进行排序和分级。

    排序规则:
    1. 按 total_score 从高到低排列 (主要规则)
    2. 如果分数非常接近 (< 3 分差距)，LLM 可以结合风险点微调
    3. 按推荐等级分组:
       - Strong Match: 总分 >= 80
       - Medium Match: 65 <= 总分 < 80
       - Weak Match: 50 <= 总分 < 65
       - Not Recommended: 总分 < 50

    参数:
        match_results: Match Agent 输出的所有候选人的评分
        llm_service: LLM 调用服务 (用于生成排序解释)
    返回:
        dict: 符合 match_schema.RankingResult 格式的排序结果
    """
    # TODO: 实现候选人排序
    # 1. 按 total_score 降序排列
    # 2. 分配推荐等级
    # 3. 生成 shortlist (Strong Match + 部分 Medium Match)
    # 4. 让 LLM 生成排序解释 (为什么这样排)

    # 注意: 排序主要是代码逻辑，不是 LLM 调用
    # LLM 只用于生成"排序解释"这个文本字段
    pass


def assign_recommendation_level(score: float) -> str:
    """
    根据总分分配推荐等级。

    参数:
        score: 候选人总匹配分数
    返回:
        str: "Strong Match" / "Medium Match" / "Weak Match" / "Not Recommended"
    """
    # 这是一个纯函数，不需要 LLM
    if score >= 80:
        return "Strong Match"
    elif score >= 65:
        return "Medium Match"
    elif score >= 50:
        return "Weak Match"
    else:
        return "Not Recommended"
