"""
app/agents/evaluation_agent.py
===============================
Evaluation Agent: 面试评价 Agent。

职责: 面试结束后，根据面试记录对候选人进行最终评价。
综合评价面试表现、技术深度、沟通能力，并判断风险点是否被解决。

输入: 面试记录 + 面试官笔记 + Candidate profile + Match result + JD profile
输出: 最终面试评价 (state.final_evaluations)
"""

from typing import Dict, Any


async def evaluate_candidate(
    interview_feedback: str,
    candidate_profile: Dict[str, Any],
    match_result: Dict[str, Any],
    jd_profile: Dict[str, Any],
    llm_service,
) -> Dict[str, Any]:
    """
    根据面试记录对候选人进行评价。

    评价维度:
    1. 技术深度 (1-10): 候选人的技术水平
    2. 沟通表达 (1-10): 表达清晰度、逻辑性
    3. 问题解决 (1-10): 应对问题的思维方式
    4. 风险解决: 面试前识别的风险点是否被澄清或消除

    参数:
        interview_feedback: 面试官记录的面试笔记和候选人回答
        candidate_profile: 候选人画像
        match_result: 匹配评分结果 (含风险点)
        jd_profile: 岗位信息
        llm_service: LLM 调用服务
    返回:
        dict: 符合 evaluation_schema.InterviewEvaluation 格式的评价
    """
    # TODO: 实现面试评价
    # 1. 构造 system prompt:
    #    角色: 资深技术面试官
    #    任务: 综合评价候选人的面试表现
    # 2. 输入面试记录、候选人画像、匹配结果
    # 3. 判断 match_result 中的 risk 是否被解决
    # 4. 给出最终推荐: Strongly Recommend / Recommend / Not Recommend

    # 重要规则:
    # - 评价必须基于面试记录中的实际回答
    # - 不能仅凭简历信息做评价
    # - 如果面试记录不足以判断某个维度，标注出来
    pass
