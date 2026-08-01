"""
tests/test_email_agent.py
==========================
Email Agent 单元测试 (不调用真实 LLM)。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_generate_email_draft_structure():
    """验证邮件草稿结构: status=draft, requires_human_approval=True。"""
    import asyncio
    from unittest.mock import patch

    async def run():
        from app.agents.email_agent import generate_email_draft

        from app.schemas.email_schema import EmailContentOutput

        with patch("app.agents.email_agent.call_llm_structured") as mock_llm:
            mock_llm.return_value = EmailContentOutput(subject="面试邀请", body="尊敬的张三，您好")

            result = await generate_email_draft(
                candidate_profile={"name":"张三","skills":["Python"]},
                job_title="Python后端",
                email_type="interview_invite",
            )

        assert result["status"] == "draft"
        assert result["requires_human_approval"] is True
        assert result["email_type"] == "interview_invite"
        assert "subject" in result
        assert "body" in result

    asyncio.run(run())


def test_generate_email_rejection_is_polite():
    """验证拒信不包含伤害性评价。"""
    import asyncio
    from unittest.mock import patch

    async def run():
        from app.agents.email_agent import generate_email_draft

        from app.schemas.email_schema import EmailContentOutput

        with patch("app.agents.email_agent.call_llm_structured") as mock_llm:
            mock_llm.return_value = EmailContentOutput(subject="感谢您的申请", body="我们很遗憾...")

            result = await generate_email_draft(
                candidate_profile={"name":"张三"},
                job_title="Python后端",
                email_type="rejection",
                evaluation_result={"recommendation":"Not Recommend","strengths":["学习能力强"]},
            )

        # 拒信不应包含"不推荐"等负面评价
        assert "Not Recommend" not in result["body"]

    asyncio.run(run())


def test_generate_email_fallback():
    """验证 LLM 返回无效 JSON 时的回退。"""
    import asyncio
    from unittest.mock import patch

    async def run():
        from app.agents.email_agent import generate_email_draft

        with patch("app.agents.email_agent.call_llm_structured") as mock_llm:
            mock_llm.side_effect = ValueError("无效输出")
            result = await generate_email_draft(
                candidate_profile={"name":"张三"},
                job_title="测试岗位",
                email_type="interview_invite",
            )

        assert result["status"] == "draft"
        assert result["requires_human_approval"] is True
        assert result["email_type"] == "interview_invite"
        assert len(result["body"]) > 0  # 有回退内容
        assert "张三" in result["body"]
        assert "候选人姓名" not in result["body"]

    asyncio.run(run())


def test_batch_generate_emails():
    """验证批量生成邮件。"""
    import asyncio
    from unittest.mock import patch

    async def run():
        from app.agents.email_agent import batch_generate_emails

        with patch("app.agents.email_agent.generate_email_draft") as mock_gen:
            mock_gen.return_value = {"email_type":"interview_invite","subject":"S","body":"B","status":"draft","requires_human_approval":True}

            result = await batch_generate_emails(
                candidate_profiles=[{"candidate_id":"C1","name":"张三"}],
                job_title="岗位",
                actions={"C1":"interview_invite"},
            )

        assert "C1" in result
        assert result["C1"]["status"] == "draft"

    asyncio.run(run())


def test_invalid_email_type_rejected():
    """验证无效 email_type 的行为 — Agent 层不校验(API层校验), 但应能生成通用邮件。"""
    # 注: email_type 校验在 API 层 (app/api/evaluation.py), Agent 层不做校验
    # 这个测试确认 Agent 不会因无效 type 崩溃
    import asyncio
    from unittest.mock import patch

    async def run():
        from app.agents.email_agent import generate_email_draft
        from app.schemas.email_schema import EmailContentOutput
        with patch("app.agents.email_agent.call_llm_structured") as mock_llm:
            mock_llm.return_value = EmailContentOutput(subject="通知", body="内容")
            result = await generate_email_draft(
                candidate_profile={"name":"张三"},
                job_title="测试",
                email_type="invalid_type",
            )
        # 不会崩溃, 返回草稿
        assert result["status"] == "draft"

    asyncio.run(run())


def test_email_replaces_candidate_name_placeholder():
    """验证模型保留占位词时，后端会替换为真实姓名。"""
    import asyncio
    from unittest.mock import patch

    async def run():
        from app.agents.email_agent import generate_email_draft
        from app.schemas.email_schema import EmailContentOutput

        with patch("app.agents.email_agent.call_llm_structured") as mock_llm:
            mock_llm.return_value = EmailContentOutput(
                subject="面试邀请",
                body="尊敬的候选人姓名，您好：欢迎参加面试。",
            )
            result = await generate_email_draft(
                candidate_profile={"name": "王小明"},
                job_title="后端工程师",
                email_type="interview_invite",
            )

        assert "王小明" in result["body"]
        assert "候选人姓名" not in result["body"]

    asyncio.run(run())
