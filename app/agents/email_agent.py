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

import re
from typing import Dict, Any, List

from app.schemas.email_schema import EmailContentOutput
from app.services.llm_service import call_llm_structured


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
    # API 会优先传入数据库中人工确认的姓名；这里仍做一次空值保护。
    candidate_name = str(candidate_profile.get("name") or "").strip() or "申请人"

    # 根据邮件类型准备提示词
    type_instructions = {
        "interview_invite": (
            "用中文生成面试邀请邮件。告知已通过筛选, 邀请参加面试。"
            "时间地点写'待HR确认后另行通知'。语气正式友好。"
        ),
        "rejection": (
            "用中文生成礼貌拒信。感谢时间和兴趣, 但本次选择了更匹配的候选人。"
            "可简要提候选人优势, 不过度解释。不输出伤害性评价。保留未来联系可能。"
        ),
        "follow_up": (
            "用中文生成面试跟进邮件。询问面试反馈, 告知后续流程。时间写'待HR确认'。"
        ),
        "next_round": (
            "用中文生成下一轮面试通知。告知已通过本轮。不填具体时间, 写'待HR确认后通知'。"
        ),
    }

    instruction = type_instructions.get(
        email_type,
        "生成一封HR邮件。不要编造时间地点薪资等信息。",
    )

    system_prompt = f"""你是专业的HR邮件撰写助手。你必须用中文输出。

═══════════════════════════════════
【语言强制要求 — 邮件正文和标题必须是中文】
═══════════════════════════════════

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
    user_message += "\n\n【重要】用中文生成邮件，并严格返回 subject 和 body 两个结构化字段。"

    try:
        # 使用 Pydantic 结构化输出，防止自由文本 JSON 被压平成截图中的一长串内容。
        structured = call_llm_structured(
            system_prompt=system_prompt,
            user_message=user_message,
            output_schema=EmailContentOutput,
        )
        result = structured.model_dump()
    except Exception as exc:
        print(f"\n[EMAIL STRUCTURED FAIL] {type(exc).__name__}: {str(exc)[:300]}\n")
        result = _build_fallback_email(candidate_name, job_title, email_type)

    subject = str(result.get("subject") or "").strip()
    body = str(result.get("body") or "").strip()

    # 如果模型仍把序列化字段塞入正文，直接换成可读模板，不展示损坏原文。
    if _looks_like_serialized_email(body):
        result = _build_fallback_email(candidate_name, job_title, email_type)
        subject = result["subject"]
        body = result["body"]

    # 最后统一替换模型可能保留的占位符，并保证正文明确包含真实姓名。
    body = _apply_candidate_name(body, candidate_name)
    if candidate_name not in body:
        body = f"尊敬的{candidate_name}，您好：\n\n{body}"

    return {
        "email_type": email_type,
        "subject": subject or f"关于{job_title}岗位的通知",
        "body": body,
        "status": "draft",
        "requires_human_approval": True,
    }


def _apply_candidate_name(body: str, candidate_name: str) -> str:
    """把常见姓名占位符替换为本次候选人的权威姓名。"""
    text = body or ""
    # 先处理带括号和不带括号的“候选人姓名”。
    text = re.sub(r"[\[【<（(]?候选人姓名[\]】>）)]?", candidate_name, text)
    # 再处理称呼位置中的泛化“候选人”，避免误改正文里的普通名词。
    text = re.sub(r"(尊敬的\s*)[\[【<（(]?候选人[\]】>）)]?", rf"\1{candidate_name}", text)
    return text


def _looks_like_serialized_email(body: str) -> bool:
    """判断正文是否误装入 JSON 字段或被压平的键值串。"""
    if not body:
        return True
    field_hits = len(re.findall(r"(?:^|\s)(?:title|subject|body)\s*[:|]", body, flags=re.IGNORECASE))
    bracket_count = sum(body.count(char) for char in "{}[]")
    return field_hits >= 1 or bracket_count >= 4


def _build_fallback_email(candidate_name: str, job_title: str, email_type: str) -> Dict[str, str]:
    """结构化生成失败时返回安全、完整且包含真实姓名的中文邮件模板。"""
    templates = {
        "interview_invite": (
            f"关于{job_title}岗位的面试邀请",
            f"尊敬的{candidate_name}，您好：\n\n"
            f"感谢您申请{job_title}岗位。您已通过初步筛选，我们诚挚邀请您参加面试。"
            "具体时间和地点待HR确认后另行通知。\n\n祝好\nHireFlow 招聘团队",
        ),
        "rejection": (
            f"关于{job_title}岗位申请的通知",
            f"尊敬的{candidate_name}，您好：\n\n"
            f"感谢您对{job_title}岗位的关注和投入。经过审慎评估，我们本次决定继续推进其他更匹配的候选人。"
            "感谢您的时间，并祝您未来求职顺利。\n\n祝好\nHireFlow 招聘团队",
        ),
        "follow_up": (
            f"关于{job_title}岗位的面试跟进",
            f"尊敬的{candidate_name}，您好：\n\n"
            f"感谢您参加{job_title}岗位的面试。相关反馈正在整理，后续安排待HR确认后另行通知。"
            "感谢您的耐心等待。\n\n祝好\nHireFlow 招聘团队",
        ),
        "next_round": (
            f"关于{job_title}岗位的下一轮面试通知",
            f"尊敬的{candidate_name}，您好：\n\n"
            f"感谢您参加{job_title}岗位的本轮面试。我们诚挚邀请您进入下一轮面试。"
            "具体时间和地点待HR确认后另行通知。\n\n祝好\nHireFlow 招聘团队",
        ),
    }
    subject, body = templates.get(
        email_type,
        (
            f"关于{job_title}岗位的通知",
            f"尊敬的{candidate_name}，您好：\n\n有关{job_title}岗位的后续安排待HR确认后另行通知。"
            "\n\n祝好\nHireFlow 招聘团队",
        ),
    )
    return {"subject": subject, "body": body}


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
