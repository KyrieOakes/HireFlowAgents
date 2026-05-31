"""
app/agents/match_agent.py
==========================
Match Agent: 候选人匹配评分 Agent。

职责: 将每个候选人与岗位描述进行对比，给出基于证据的评分。
这是系统的核心 Agent，决定候选人进入下一轮还是被淘汰。

输入: JD profile + Candidate profile + RAG 证据
输出: 匹配评分结果 (state.match_results)

评分 Rubric (总分 100):
- 技术技能: 30 分
- 项目相关性: 20 分
- 工作经验: 15 分
- 教育背景: 10 分
- 领域相关性: 10 分
- 沟通表达: 5 分
- 风险扣分: -10 分
"""

from typing import Dict, Any, List


async def match_candidate(
    jd_profile: Dict[str, Any],
    candidate_profile: Dict[str, Any],
    evidence: List[Dict[str, Any]],
    rubric: Dict[str, Any],
    llm_service,
) -> Dict[str, Any]:
    """
    对单个候选人进行匹配评分。

    这是 Match Agent 的核心函数。它不只是一个简单的关键词匹配，
    而是让 LLM 理解 JD 要求和候选人背景后，给出有推理的评分。

    参数:
        jd_profile: 结构化岗位信息
        candidate_profile: 结构化候选人画像
        evidence: 从简历中检索到的相关证据 (RAG 结果)
        rubric: 评分标准和各维度权重
        llm_service: LLM 调用服务
    返回:
        dict: 符合 match_schema.MatchResult 格式的评分结果
    """
    # TODO: 实现匹配评分逻辑
    # 1. 构造 system prompt:
    #    角色: 资深招聘专家和技术面试官
    #    任务: 根据 JD 要求和 Rubric 对候选人评分
    #    规则: 每个分数必须基于简历证据
    # 2. 构造 user message:
    #    包含 jd_profile, candidate_profile, evidence, rubric
    # 3. 调用 call_llm_structured() 约束输出
    # 4. 计算 total_score = 各维度分数之和
    # 5. 如果证据不足，降低对应维度分数并标注

    # 重要规则:
    # - 不能编造候选人没有的经验/技能
    # - 每个得分点都要有 evidence 支撑
    # - risk_penalty 需要有明确的扣分理由
    pass


async def batch_match_candidates(
    jd_profile: Dict[str, Any],
    candidate_profiles: List[Dict[str, Any]],
    evidence_by_candidate: Dict[str, List[Dict[str, Any]]],
    rubric: Dict[str, Any],
    llm_service,
) -> List[Dict[str, Any]]:
    """
    批量对多个候选人进行匹配评分。

    参数:
        jd_profile: 结构化岗位信息 (同一个 JD 用于所有候选人)
        candidate_profiles: 所有候选人的画像列表
        evidence_by_candidate: 每个候选人的 RAG 证据
        rubric: 评分标准
        llm_service: LLM 调用服务
    返回:
        List[dict]: 所有候选人的匹配评分结果
    """
    # TODO: 实现批量匹配
    # 1. 遍历每个候选人
    # 2. 获取该候选人的 RAG 证据
    # 3. 调用 match_candidate() 评分
    # 4. 收集所有结果
    pass
