"""
app/agents/email_agent.py
==========================
Email Agent: HR 邮件草稿生成 Agent。

职责: 根据候选人状态生成不同类型的 HR 邮件草稿。
系统只生成草稿，发送前必须经过人工审核。

输入: Candidate profile + 候选人状态 + 面试结果 + 邮件类型
输出: 邮件草稿 (state.email_drafts)

邮件类型:
- interview_invite: 面试邀请
- rejection: 拒信
- follow_up: 后续跟进
- next_round: 下一轮面试通知
"""

from typing import Dict, Any


async def generate_email_draft(
    candidate_profile: Dict[str, Any],
    job_title: str,
    email_type: str,
    evaluation_result: Dict[str, Any] = None,
    llm_service=None,
) -> Dict[str, Any]:
    """
    生成单封 HR 邮件草稿。

    邮件内容会根据候选人信息和岗位信息进行个性化填充。
    不同邮件类型使用不同的语气和内容模板。

    参数:
        candidate_profile: 候选人画像 (用于个性化称呼和内容)
        job_title: 岗位名称
        email_type: 邮件类型 ("interview_invite"/"rejection"/"follow_up"/"next_round")
        evaluation_result: 面试评价 (对于拒信或下一轮通知，需要引用评价内容)
        llm_service: LLM 调用服务
    返回:
        dict: 符合 evaluation_schema.EmailDraft 格式的邮件草稿
    """
    # TODO: 实现邮件草稿生成
    # 1. 根据 email_type 选择合适的系统提示词:
    #    - 面试邀请: 正式、友好、包含面试时间和职位信息
    #    - 拒信: 礼貌、有温度、感谢参与、可提及候选人优势
    #    - follow_up: 简洁、提醒、附上后续步骤
    #    - next_round: 恭喜通过、预告下一轮内容
    # 2. 调用 LLM 填充邮件模板
    # 3. 确保邮件中包含候选人姓名 (避免群发感)
    # 4. 标记 status 为 "draft"

    # 重要规则:
    # - 绝对不能填写虚假信息 (如不确认的面试时间)
    # - 对于拒信，尽量正面、不说伤害性的话
    # - 必须包含候选人姓名，不能是通用模板
    pass


async def batch_generate_emails(
    candidate_profiles: list,
    job_title: str,
    actions: Dict[str, str],  # {candidate_id: email_type}
    evaluation_results: Dict[str, Dict[str, Any]],
    llm_service,
) -> Dict[str, Dict[str, str]]:
    """
    为多个候选人批量生成邮件草稿。

    参数:
        candidate_profiles: 候选人画像列表
        job_title: 岗位名称
        actions: 每个候选人的邮件类型映射
        evaluation_results: 每个候选人的面试评价
        llm_service: LLM 调用服务
    返回:
        dict: {email_type: {subject, body}}
    """
    # TODO: 实现批量邮件生成
    pass
