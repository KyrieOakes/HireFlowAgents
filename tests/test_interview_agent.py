"""
tests/test_interview_agent.py
==============================
Interview Agent 单元测试 (不调用真实 LLM)。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_build_prompt_includes_jd_info():
    """验证提示词构造包含 JD 关键信息。"""
    from app.agents.interview_agent import _build_question_prompt

    prompt = _build_question_prompt(
        jd_profile={"job_title": "Python后端", "required_skills": ["Python","FastAPI"], "technical_requirements": ["Docker"], "soft_skills": ["沟通能力"]},
        candidate_profile={"name":"测试","skills":["Python"],"projects":[{"name":"API项目","description":"FastAPI后端","technologies":["FastAPI"]}],"work_experience":[]},
        match_result={"risks":["经验不足"],"total_score":75,"recommendation":"Medium Match"},
    )
    assert "Python后端" in prompt
    assert "Python" in prompt
    assert "API项目" in prompt
    assert "经验不足" in prompt


def test_question_structure_is_valid():
    """验证 generate_questions 返回格式正确 (mock LLM)。"""
    import asyncio
    from unittest.mock import patch, MagicMock

    async def run():
        from app.agents.interview_agent import generate_questions
        # Mock call_llm 返回预设 JSON
        with patch("app.agents.interview_agent.call_llm") as mock_llm:
            mock_llm.return_value = '[{"question_type":"technical","question":"什么是FastAPI?","purpose":"测试技术"}]'
            result = await generate_questions(
                jd_profile={"job_title":"测试","required_skills":["Python"],"technical_requirements":[],"soft_skills":[]},
                candidate_profile={"name":"张三","skills":["Python"],"projects":[],"work_experience":[]},
                match_result={"risks":[],"total_score":80,"recommendation":"Strong Match"},
            )
        assert isinstance(result, list)
        assert len(result) >= 1
        assert result[0]["question_type"] == "technical"
        assert "question" in result[0]
        assert "purpose" in result[0]

    asyncio.run(run())


def test_batch_generate_questions():
    """验证批量生成问题函数。"""
    import asyncio
    from unittest.mock import patch

    async def run():
        from app.agents.interview_agent import batch_generate_questions
        with patch("app.agents.interview_agent.generate_questions") as mock_gen:
            mock_gen.return_value = [{"question_type":"tech","question":"Q","purpose":"P"}]
            result = await batch_generate_questions(
                jd_profile={},
                candidate_profiles=[{"candidate_id":"C1"},{"candidate_id":"C2"}],
                match_results=[{"candidate_id":"C1"},{"candidate_id":"C2"}],
                selected_ids=["C1"],
                llm_service=None,
            )
        assert "C1" in result
        assert "C2" not in result  # 没选中的不生成
        assert len(result["C1"]) == 1

    asyncio.run(run())


def test_json_parse_fallback():
    """验证 LLM 返回无效 JSON 时的回退逻辑。"""
    import asyncio
    from unittest.mock import patch

    async def run():
        from app.agents.interview_agent import generate_questions
        with patch("app.agents.interview_agent.call_llm") as mock_llm:
            mock_llm.return_value = "这不是JSON"
            result = await generate_questions(
                jd_profile={"job_title":"测试","required_skills":["Python"],"technical_requirements":[],"soft_skills":[]},
                candidate_profile={"name":"张三","skills":["Python"],"projects":[],"work_experience":[]},
                match_result={"risks":[],"total_score":80,"recommendation":"Strong"},
            )
        # 即使解析失败, 也要返回有效结构
        assert isinstance(result, list)
        assert len(result) >= 1
        assert "question" in result[0]

    asyncio.run(run())
