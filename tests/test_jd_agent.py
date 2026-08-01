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


def test_analyze_jd_cleans_corruption_and_recovers_from_source():
    """使用真实 ByteIntern JD 验证标题、职责和要求不会被模型乱码污染。"""
    async def run():
        from app.agents.jd_agent import analyze_jd
        from app.schemas.jd_schema import JobDescription

        jd_text = """**AI Agent开发实习生-计算**
上海
实习
研发 - 后端
ByteIntern
职位 ID：A31360A
**职位描述**
ByteIntern：面向2027届毕业生（2026年9月-2027年8月期间毕业），为符合岗位要求的同学提供转正机会。
团队介绍：字节跳动基础设施计算团队，专注构建面向大模型与 AI Agent 时代的 AI-Native Infra。
1、构建高性能、多语言版本的Agent开发框架，与Agent Infra平台协同服务用户；
2、设计并开发企业级Agent系统，涵盖多Agent协作、记忆、知识、鉴权、观测等全生命周期；
3、探索业界最新的技术或工具，如Agent Skills、OpenCode、Moltbot等应用和落地。
**职位要求**
1、2027届本科及以上学历在读，计算机、通信等相关专业；
2、掌握算法、数据结构等基础知识，至少熟练使用一门编程语言（C/C++/Python/Go/Java等）；
3、积极乐观，责任心强，工作认真细致，具有良好的团队沟通与协作能力；
4、热爱编程，有较强的学习能力，有强烈的求知欲、好奇心和进取心；
5、有Agent开发、Agent框架、Agent Skills等相关经验者优先。"""

        with patch("app.agents.jd_agent.call_llm_structured") as mock:
            # 这些值复现截图中的职位 ID、韩文、字节转义和错误年份污染。
            mock.return_value = JobDescription(
                job_title="\\姓\\줄A31360A: AI Agent开发实习生-计算",
                required_skills=["熟练使用一门编程语言（C/C++/Python/Go/Java等）", "掌握算法、数据结构基础知识"],
                preferred_skills=["热爱编程", "开쓽\\xE9A8\\"],
                responsibilities=["构建高性能、多语言版本的Agent开发框架", "左좲\\xE7A0\": ,"],
                education_requirements=["202处届本科及以上学历在读", "주\\xE6A1臒"],
                company="字节跳动",
                technical_requirements=["算法", "数据结构"],
                soft_skills=["积极乐观", "你슨\\xE7B5\": ,"],
            )
            result = await analyze_jd(jd_text)

        assert result["job_title"] == "AI Agent开发实习生-计算"
        assert result["location"] == "上海"
        assert result["company"] == "字节跳动"
        assert len(result["responsibilities"]) == 3
        assert result["responsibilities"][1].startswith("设计并开发企业级Agent系统")
        assert any(item.startswith("2027届本科及以上学历") for item in result["education_requirements"])
        assert any("Agent Skills" in item and "优先" in item for item in result["preferred_skills"])
        assert any("算法、数据结构" in item for item in result["required_skills"])
        assert any("熟练使用一门编程语言" in item for item in result["required_skills"])
        assert "Python" in result["technical_requirements"]
        assert "Agent Skills" in result["technical_requirements"]
        assert "热爱编程" not in result["preferred_skills"]
        assert all("202处届" not in item for item in result["education_requirements"])

        # 所有业务字段递归检查，确保没有韩文、反斜杠或字节转义残留。
        business_text = str({key: value for key, value in result.items() if key != "rubric"})
        assert not re.search(r"[\uac00-\ud7af]", business_text)
        assert "\\x" not in business_text
        assert "\\" not in business_text

    import re
    asyncio.run(run())
