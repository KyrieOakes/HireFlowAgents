"""
app/agents/interview_agent.py
==============================
Interview Agent: 面试问题生成 Agent。

职责: 为进入面试的候选人生成定制化面试问题。
问题是"定制化"的，因为会根据每个候选人的简历、优势和风险点来设计。

输入: JD profile + Candidate profile + Match result + 风险点 + 证据
输出: 定制化面试问题集 (state.interview_questions)

问题类型:
- 技术问题 (technical): 考察技术能力
- 项目深挖 (project_deep_dive): 验证简历中的项目经验真实性
- 行为问题 (behavioral): 考察软技能和团队协作
- 风险验证 (risk_verification): 专门针对简历中的疑点提问
"""

from typing import Dict, Any, List


async def generate_questions(
    jd_profile: Dict[str, Any],
    candidate_profile: Dict[str, Any],
    match_result: Dict[str, Any],
    llm_service,
) -> List[Dict[str, Any]]:
    """
    为单个候选人生成定制化面试问题。

    每个候选人得到 6-10 个问题，覆盖 4 种问题类型。
    问题需要:
    - 与岗位要求相关 (基于 jd_profile)
    - 与候选人背景相关 (基于 candidate_profile)
    - 验证匹配结果中的风险点 (基于 match_result 的 risks)

    参数:
        jd_profile: 结构化岗位信息
        candidate_profile: 候选人的结构化画像
        match_result: 该候选人的匹配结果 (含风险点)
        llm_service: LLM 调用服务
    返回:
        List[dict]: 面试问题列表，每个问题含 type, question, purpose
    """
    # TODO: 实现面试问题生成
    # 1. 构造 system prompt:
    #    角色: 资深技术面试官
    #    任务: 生成定制化面试问题
    #    规则:
    #      - 技术问题基于 JD 的 required_skills
    #      - 项目深挖基于 candidate 的 projects
    #      - 行为问题基于 JD 的 soft_skills
    #      - 风险验证基于 match_result 的 risks
    # 2. 确保问题数量合理 (每种 2-3 题)
    # 3. 每个问题都要有明确的"提问目的"

    # 示例: 如果候选人声称有 RAG 经验但没写具体细节
    # -> 风险验证问题: "你在 RAG 项目中是如何做 chunking 和 embedding 的?"
    pass


async def batch_generate_questions(
    jd_profile: Dict[str, Any],
    candidate_profiles: List[Dict[str, Any]],
    match_results: List[Dict[str, Any]],
    selected_ids: List[str],
    llm_service,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    为所有选中的候选人批量生成面试问题。

    参数:
        jd_profile: 岗位信息
        candidate_profiles: 所有候选人画像
        match_results: 所有匹配结果
        selected_ids: 被选中进入面试的候选人 ID 列表
        llm_service: LLM 调用服务
    返回:
        dict: {candidate_id: [问题列表]}
    """
    # TODO: 实现批量问题生成
    # 1. 遍历 selected_ids
    # 2. 找到对应的 candidate_profile 和 match_result
    # 3. 调用 generate_questions()
    # 4. 组织为字典返回
    pass
