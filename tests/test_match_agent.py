"""
tests/test_match_agent.py
=========================
Match Agent 单元测试 (mock LLM)。
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from unittest.mock import patch


def test_match_candidate_structure():
    """验证匹配评分返回完整字段。"""
    async def run():
        from app.agents.match_agent import match_candidate
        from app.schemas.match_schema import MatchResult, DimensionScores

        with patch("app.agents.match_agent.call_llm_structured") as mock:
            mock.return_value = MatchResult(
                candidate_id="C001",
                total_score=85.0,
                dimension_scores=DimensionScores(
                    technical_skills=28, project_relevance=18,
                    experience=12, education=8, domain_relevance=9,
                    communication=4, risk_penalty=-4,
                ),
                strengths=["技能匹配度高"],
                risks=["经验偏少"],
                recommendation="Strong Match",
                summary="总体匹配良好",
            )
            result = await match_candidate(
                jd_profile={"job_title":"Python后端","required_skills":["Python"]},
                candidate_profile={"candidate_id":"C001","name":"张三","skills":["Python"]},
            )
        assert result["total_score"] == 85.0
        assert result["recommendation"] == "Strong Match"
        assert "dimension_scores" in result
        assert result["candidate_id"] == "C001"
    asyncio.run(run())


def test_build_match_prompt():
    """验证提示词包含关键信息。"""
    from app.agents.match_agent import _build_match_prompt
    prompt = _build_match_prompt(
        jd_profile={"job_title":"Python后端","required_skills":["Python","FastAPI"],"preferred_skills":["Docker"],"responsibilities":["开发API"],"education_requirements":["本科"],"technical_requirements":["FastAPI"],"soft_skills":["沟通"],"experience_requirements":"0-3年"},
        candidate_profile={"candidate_id":"C1","name":"张三","skills":["Python","FastAPI","Docker"],"education":[{"degree":"学士","school":"清华","major":"CS"}],"projects":[{"name":"API","description":"后端开发","technologies":["FastAPI"]}],"work_experience":[{"title":"实习生","company":"某公司","duration":"2023-2024"}],"estimated_years_of_experience":1},
    )
    assert "Python后端" in prompt
    assert "张三" in prompt
    assert "Python" in prompt
    assert "清华" in prompt


def test_batch_match():
    """验证批量匹配。"""
    async def run():
        from app.agents.match_agent import batch_match_candidates
        from app.schemas.match_schema import MatchResult, DimensionScores

        with patch("app.agents.match_agent.call_llm_structured") as mock:
            mock.return_value = MatchResult(
                candidate_id="C1", total_score=80.0,
                dimension_scores=DimensionScores(technical_skills=25,project_relevance=15,experience=10,education=8,domain_relevance=7,communication=4,risk_penalty=0),
                strengths=[], risks=[], recommendation="Strong Match",
            )
            results = await batch_match_candidates(
                jd_profile={"job_title":"测试"},
                candidate_profiles=[{"candidate_id":"C1","name":"A","skills":[]},{"candidate_id":"C2","name":"B","skills":[]}],
            )
        assert len(results) == 2
    asyncio.run(run())
