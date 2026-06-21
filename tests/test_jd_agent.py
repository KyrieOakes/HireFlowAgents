"""
tests/test_jd_agent.py
=======================
JD Agent 单元测试 (mock LLM, 不调真实 API)。
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from unittest.mock import patch


def test_analyze_jd_structure():
    """验证 JD 解析返回必要字段。"""
    async def run():
        from app.agents.jd_agent import analyze_jd
        with patch("app.agents.jd_agent.call_llm_structured") as mock:
            # 模拟 LLM 返回
            from app.schemas.jd_schema import JobDescription
            mock.return_value = JobDescription(
                job_title="Python后端",
                required_skills=["Python","FastAPI"],
                preferred_skills=["Docker"],
                responsibilities=["开发API"],
                education_requirements=["本科"],
                technical_requirements=["FastAPI"],
                soft_skills=["沟通"],
            )
            result = await analyze_jd("岗位: Python后端, 需要FastAPI")
        assert result["job_title"] == "Python后端"
        assert "rubric" in result  # 自动生成 Rubric
        assert result["rubric"]["technical_skills"]["max_score"] == 30
    asyncio.run(run())


def test_rubric_structure():
    """验证 Rubric 各维度有合理的 max_score。"""
    from app.agents.jd_agent import _generate_rubric
    rubric = _generate_rubric({"job_title":"测试"})
    assert rubric["total"] == 100
    assert rubric["technical_skills"]["max_score"] == 30
    assert rubric["risk_penalty"]["max_score"] == -10


def test_analyze_jd_fallback():
    """验证 LLM 返回空字段时的处理。"""
    async def run():
        from app.agents.jd_agent import analyze_jd
        with patch("app.agents.jd_agent.call_llm_structured") as mock:
            from app.schemas.jd_schema import JobDescription
            mock.return_value = JobDescription(
                job_title="", required_skills=[], preferred_skills=[],
                responsibilities=[], education_requirements=[],
                technical_requirements=[], soft_skills=[],
            )
            result = await analyze_jd("空JD")
        # 不应崩溃
        assert "rubric" in result
        assert result["job_title"] == ""
    asyncio.run(run())
