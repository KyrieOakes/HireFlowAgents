"""
app/agents/email_agent.py
==========================
Email Agent: HR 邮件草稿生成 Agent。

职责: 根据候选人状态生成 HR 邮件草稿。
系统只生成草稿, 发送前必须人工审核。

输入: Candidate profile + 岗位名称 + 邮件类型 + 面试评价(可选)
输出: 邮件草稿 (subject + body + status=draft)

邮件类型:
- interview_invite: 面试邀请
- rejection: 拒信
- follow_up: 后续跟进
- next_round: 下一轮面试通知

重要规则:
- 只生成草稿, 不自动发送
- requires_human_approval 必须为 true
- 不能编造具体时间、地点、薪资、录用承诺
- 拒信要礼貌、克制
"""

from typing import Dict, Any, List
from app.services.llm_service import call_llm
from app.utils.config import settings


async def generate_email_draft(
    candidate_profile: Dict[str, Any],
    job_title: str,
    email_type: str,
    evaluation_result: Dict[str, Any] = None,
    llm_service=None,
) -> Dict[str, Any]:
    """
    生成单封 HR 邮件草稿。

    参数:
        candidate_profile: 候选人画像 (含 name, skills 等)
        job_title: 岗位名称
        email_type: 邮件类型 (interview_invite/rejection/follow_up/next_round)
        evaluation_result: 面试评价 (拒信/下一轮时引用评价)
        llm_service: 保留
    返回:
        dict: {"email_type": ..., "subject": ..., "body": ..., "status": "draft", "requires_human_approval": True}
    """
    candidate_name = candidate_profile.get("name", "候选人")

    # 根据邮件类型准备提示词
    type_instructions = {
        "interview_invite": (
            "生成一封面试邀请邮件。告知候选人已通过初步筛选, 邀请参加面试。"
            "不要填写具体面试时间和地点, 写'待HR确认后另行通知'。语气正式友好。"
        ),
        "rejection": (
            "生成一封礼貌的拒信。感谢候选人的时间和兴趣, 但本次选择了更匹配的候选人。"
            "可以简要提及候选人的优势(基于简历), 但不要过度解释拒绝原因。"
            "不要输出伤害性评价或具体评分。保留未来联系的可能性。"
        ),
        "follow_up": (
            "生成一封面试跟进邮件。询问候选人对面试的反馈, 告知后续流程和时间安排。"
            "具体时间写'待HR确认'。"
        ),
        "next_round": (
            "生成一封下一轮面试通知邮件。告知候选人已通过本轮面试, 进入下一轮。"
            "不要填写具体面试时间, 写'待HR确认后通知'。可以简要肯定候选人本轮表现。"
        ),
    }

    instruction = type_instructions.get(
        email_type,
        "生成一封HR邮件。不要编造时间地点薪资等信息。",
    )

    system_prompt = f"""你是专业的HR邮件撰写助手。输出必须使用中文。

【规则 - 最高优先级】
- 你是生成草稿, 不是发送邮件
- 不要编造: 具体面试时间、地点、薪资、录用承诺
- 需要填写时间和地点的地方写"待HR确认后另行通知"
- 拒信要礼貌、克制、温暖
- 邮件中必须包含候选人姓名和岗位名称
- 使用正式的商业邮件格式
- 开头: 尊敬的[候选人姓名]
- 结尾: 祝好\nHireFlow 招聘团队"""

    # 构建用户消息
    user_lines = [
        instruction,
        "",
        f"岗位名称: {job_title}",
        f"候选人姓名: {candidate_name}",
    ]

    if candidate_profile.get("skills"):
        user_lines.append(f"候选人技能: {', '.join(candidate_profile['skills'][:5])}")

    if evaluation_result and email_type in ("rejection", "next_round", "follow_up"):
        rec = evaluation_result.get("recommendation", "")
        if rec:
            user_lines.append(f"面试评价建议: {rec}")
        strengths = evaluation_result.get("strengths", [])
        if strengths:
            user_lines.append(f"候选人优势: {', '.join(strengths[:3])}")

    user_message = "\n".join(user_lines)
    user_message += "\n\n请生成邮件草稿。只输出 JSON: {\"subject\": \"...\", \"body\": \"...\"}"

    # 调用 LLM
    response = call_llm(
        system_prompt=system_prompt,
        user_message=user_message,
    )

    # 解析 JSON
    import json
    try:
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        result = json.loads(text.strip())
    except json.JSONDecodeError:
        # 回退: 用原始文本作为 body
        result = {
            "subject": f"关于{job_title}岗位的通知",
            "body": response,
        }

    return {
        "email_type": email_type,
        "subject": result.get("subject", f"关于{job_title}岗位的通知"),
        "body": result.get("body", response),
        "status": "draft",
        "requires_human_approval": True,
    }


async def batch_generate_emails(
    candidate_profiles: List[Dict[str, Any]],
    job_title: str,
    actions: Dict[str, str],
    evaluation_results: Dict[str, Dict[str, Any]] = None,
    llm_service=None,
) -> Dict[str, Dict[str, Any]]:
    """
    批量生成邮件草稿。

    参数:
        candidate_profiles: 候选人画像列表
        job_title: 岗位名称
        actions: {candidate_id: email_type} 每个候选人的邮件类型
        evaluation_results: {candidate_id: evaluation} 每个候选人的评价
        llm_service: 保留
    返回:
        dict: {candidate_id: 邮件草稿}
    """
    profile_map = {p.get("candidate_id", ""): p for p in candidate_profiles}
    eval_map = evaluation_results or {}

    results = {}
    for cid, email_type in actions.items():
        profile = profile_map.get(cid)
        if profile:
            results[cid] = await generate_email_draft(
                candidate_profile=profile,
                job_title=job_title,
                email_type=email_type,
                evaluation_result=eval_map.get(cid),
            )

    return results
