"""
tests/test_resume_agent.py
==========================
Resume Agent 单元测试 (mock LLM)。
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from unittest.mock import patch


def test_parse_resume_structure():
    """验证简历解析返回嵌套结构。"""
    async def run():
        from app.agents.resume_agent import parse_resume
        from app.schemas.resume_schema import CandidateProfile, Education, Project, WorkExperience

        with patch("app.agents.resume_agent.call_llm_structured") as mock:
            mock.return_value = CandidateProfile(
                candidate_id="C001",
                name="张三",
                email="zhang@test.com",
                education=[Education(degree="学士", school="清华大学", major="计算机")],
                skills=["Python","FastAPI"],
                projects=[Project(name="API项目", description="开发后端", technologies=["FastAPI"])],
                work_experience=[WorkExperience(company="某公司", title="实习生", description=["写代码"])],
                certifications=[],
                strengths=["技能匹配"],
                risks=["经验不足"],
                missing_info=["无证书"],
                estimated_years_of_experience=0.5,
            )
            result = await parse_resume("简历: 张三, 清华...", "C001")

        assert result["candidate_id"] == "C001"
        assert result["name"] == "张三"
        assert len(result["education"]) == 1
        assert result["education"][0]["school"] == "清华大学"
        assert len(result["skills"]) == 2
        assert len(result["projects"]) == 1
        assert result["strengths"] == ["技能匹配"]
        assert result["risks"] == ["经验不足"]
    asyncio.run(run())


def test_batch_parse_resumes():
    """验证批量解析。"""
    async def run():
        from app.agents.resume_agent import batch_parse_resumes
        from app.schemas.resume_schema import CandidateProfile

        with patch("app.agents.resume_agent.call_llm_structured") as mock:
            mock.return_value = CandidateProfile(
                candidate_id="", name="测试", email="",
                education=[], skills=["Python"], projects=[], work_experience=[],
                certifications=[], strengths=[], risks=[], missing_info=[],
            )
            results = await batch_parse_resumes({"C1":"简历1", "C2":"简历2"})
        assert len(results) == 2
    asyncio.run(run())


def test_empty_resume_handling():
    """验证空简历不崩溃。"""
    async def run():
        from app.agents.resume_agent import parse_resume
        from app.schemas.resume_schema import CandidateProfile

        with patch("app.agents.resume_agent.call_llm_structured") as mock:
            mock.return_value = CandidateProfile(
                candidate_id="", name="", email="",
                education=[], skills=[], projects=[], work_experience=[],
                certifications=[], strengths=[], risks=[], missing_info=[],
            )
            result = await parse_resume("", "C001")
        assert result["skills"] == []
        assert result["name"] == ""
    asyncio.run(run())


def test_parse_resume_cleans_corrupted_llm_output():
    """验证 LLM 输出乱码时，系统会用简历原文兜底关键字段。"""
    async def run():
        from app.agents.resume_agent import parse_resume
        from app.schemas.resume_schema import CandidateProfile, Education, Project, WorkExperience

        resume_text = """
姓名: 王小明
邮箱: 2297734484@qq.com
电话: +86 153 9764 7192
技能: Python, RAG, LangGraph, FastAPI
项目: HireFlowAgents AI 招聘系统
"""

        with patch("app.agents.resume_agent.call_llm_structured") as mock:
            mock.return_value = CandidateProfile(
                candidate_id="C001",
                name="\\你\\\\ud83c\\udd70",
                email="\\n2297734484@qq.com\\r\\n",
                phone="+86 153-9764-7192",
                education=[
                    Education(
                        degree="\\ud83d\\\\uddfa",
                        school="彩\\\\uft4\\uC2 \\E7%A6\\\\x81",
                        major="秋-\\\"AI\\",
                    )
                ],
                skills=[
                    "\\秋-\\\"AI\\싰 产品与应用:\\RAG \\C5D4 \\叨싰",
                    "Python",
                    "LangGraph",
                ],
                projects=[
                    Project(
                        name="HireFlowAgents：AI\\\\xC9C4贚 \\얳",
                        description="设计并开发面向招聘场景的 AI 系统。",
                        technologies=["Docker", "\\秋-后端与接口"],
                    )
                ],
                work_experience=[
                    WorkExperience(
                        company="\\中얳 CA",
                        title="\\ud83d\\",
                        description=["参与用户管理系统开发和测试。"],
                    )
                ],
                certifications=[],
                strengths=["\\슱取 \\xC5C4 AI 产品与应用方面的实践经验"],
                risks=["经验较少"],
                missing_info=[],
                estimated_years_of_experience=None,
            )

            result = await parse_resume(resume_text, "C001")

        assert result["candidate_id"] == "C001"
        assert result["name"] == "王小明"
        assert result["email"] == "2297734484@qq.com"
        assert result["phone"] == "+86 153 9764 7192"
        assert "Python" in result["skills"]
        assert "LangGraph" in result["skills"]
        assert all("\\x" not in skill and "\\u" not in skill for skill in result["skills"])
        assert result["education"] == []
        assert result["work_experience"][0]["description"] == ["参与用户管理系统开发和测试。"]
    asyncio.run(run())
