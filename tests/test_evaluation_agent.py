"""
tests/test_evaluation_agent.py
===============================
Evaluation Agent 单元测试 (不调用真实 LLM)。
"""

import sys
import os
from unittest.mock import AsyncMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_evaluate_candidate_mock():
    """验证 evaluate_candidate 返回结构完整 (mock LLM)。"""
    import asyncio
    from unittest.mock import patch

    async def run():
        from app.agents.evaluation_agent import evaluate_candidate

        from app.schemas.evaluation_schema import InterviewEvaluationOutput, RiskResolution

        with patch("app.agents.evaluation_agent.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            # 模拟结构化 LLM 返回，测试 Pydantic 数据能完整流入 API。
            mock_llm.return_value = InterviewEvaluationOutput(
                technical_depth_score=8,
                communication_score=7,
                problem_solving_score=6,
                risk_resolution=[RiskResolution(risk="经验不足", status="resolved", reason="实际有2年经验")],
                strengths=["表达清晰"],
                concerns=[],
                summary="表现良好",
                recommendation="Recommend",
            )

            result = await evaluate_candidate(
                interview_feedback="候选人回答流畅, 技术问题都答对了",
                candidate_profile={"name":"张三","skills":["Python"]},
                match_result={"risks":["经验不足"],"total_score":75,"recommendation":"Medium"},
                jd_profile={"job_title":"Python后端"},
            )

        # 验证必要字段
        assert result["requires_human_review"] is True
        assert "recommendation" in result
        assert "strengths" in result
        assert "concerns" in result
        assert "risk_resolution" in result
        # 分数范围
        assert 1 <= result["technical_depth_score"] <= 10

    asyncio.run(run())


def test_evaluate_candidate_fallback():
    """验证 LLM 返回无效 JSON 时的回退。"""
    import asyncio
    from unittest.mock import patch

    async def run():
        from app.agents.evaluation_agent import evaluate_candidate

        with patch("app.agents.evaluation_agent.call_llm_structured", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = ValueError("无效结构化输出")

            result = await evaluate_candidate(
                interview_feedback="简单反馈",
                candidate_profile={"name":"张三","skills":["Python"]},
                match_result={"risks":[],"total_score":80},
                jd_profile={"job_title":"测试"},
            )

        assert result["requires_human_review"] is True
        assert result["recommendation"] == "Hold"  # 默认值
        assert "technical_depth_score" not in result["summary"]
        assert "简单反馈" in result["summary"]

    asyncio.run(run())


def test_build_eval_prompt():
    """验证提示词构造包含面试反馈。"""
    from app.agents.evaluation_agent import _build_eval_prompt

    prompt = _build_eval_prompt(
        interview_feedback="候选人表现优异",
        candidate_profile={"name":"张三","skills":["Python"]},
        match_result={"risks":["风险1"],"total_score":80,"recommendation":"Strong"},
        jd_profile={"job_title":"Python后端"},
    )
    assert "候选人表现优异" in prompt
    assert "风险1" in prompt
    assert "Python后端" in prompt
