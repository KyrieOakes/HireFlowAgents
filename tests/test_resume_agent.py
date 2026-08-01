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


def test_parse_resume_uses_raw_text_when_llm_semantic_fields_are_wrong():
    """验证 LLM 把章节标题当姓名、把列表打乱时，原文解析结果优先。"""
    async def run():
        from app.agents.resume_agent import parse_resume
        from app.schemas.resume_schema import CandidateProfile, Education, Project, WorkExperience

        resume_text = """范瑞杰
+86 153-9764-7192 | 2297734484@qq.com
GitHub: https://github.com/KyrieOakes?tab=repositories

求职方向
AI 产品助理 / 数据产品分析师 / AI 应用与数字化方向

教育经历
悉尼科技大学
人工智能 硕士
2025.02 - 2026.12

悉尼大学
数据科学 本科
2022.02 - 2024.12

项目经历

HireFlowAgents：AI 招聘辅助平台
2026.06 - 2026.07
设计并开发一个面向招聘场景的 AI Agent 系统，目标是提升简历筛选、岗位匹配、候选人排序和面试准备的效率。
参与 FastAPI 接口设计，包括 workflow 启动、状态查询和审核后恢复流程。

Local RAG System：企业知识库问答系统
2026.05 - 2026.06
构建本地知识库问答系统，用于解决企业内部文档检索效率低、知识分散和问答不可追溯等问题。
设计 retrieval evaluation 指标体系，使用 Recall@K、Precision@K、MRR、NDCG@K 分析系统检索质量。

Financial News Sentiment Classification：金融新闻情绪分析
2025.08 - 2025.10
基于金融新闻标题构建情绪分类模型，帮助用户快速判断新闻可能带来的市场情绪影响。
使用 BERT 微调模型，并通过 accuracy、F1-score 和 confusion matrix 评估模型表现。

卡片风险预测与机器学习建模
2025.02 - 2025.04
基于结构化数据完成风险预测建模，负责数据清洗、特征工程、多模型训练和结果对比。
通过 Logistic Regression、Random Forest、XGBoost、SVM 等模型对比。

实习经历
四川 CA
产品研发实习生
2024.01 - 2024.02
参与用户管理系统开发和测试，了解企业级平台、数字认证产品和客户服务流程。
学习数字认证、权限管理和基础加密概念，理解安全产品在政企客户中的应用场景。

技能
AI 产品与应用：RAG · AI Agent · LangGraph · Workflow Design · Human-in-the-Loop · LLM 应用
数据分析：Pandas · NumPy · Matplotlib · 数据清洗 · 特征工程 · 指标评估
机器学习：Scikit-learn · BERT · XGBoost · Random Forest · SVM · Logistic Regression
后端与接口：FastAPI · Pydantic · SQL · RESTful API
项目协作：Git/GitHub · pytest · Docker · Scrum · Jupyter Notebook"""

        with patch("app.agents.resume_agent.call_llm_structured") as mock:
            mock.return_value = CandidateProfile(
                candidate_id="C001",
                name="求职方向",
                email="2297734484@qq.com",
                phone="+86 153-9764-7192",
                education=[
                    Education(degree=", }", school="悉尼科技大学", major="")
                ],
                skills=[", }, {,}, {}, {} ],", '"+86 153-9764-7192"],,'],
                projects=[
                    Project(
                        name="HireFlowAgents：AI 招聘辅助平台",
                        description="",
                        technologies=["RAG", "FastAPI"],
                        role="设计并开发",
                    )
                ],
                work_experience=[
                    WorkExperience(
                        company="",
                        title="",
                        duration="—",
                        description=["参与用户管理系统开发和测试。"],
                    )
                ],
                certifications=[],
                strengths=[],
                risks=[],
                missing_info=[],
                estimated_years_of_experience=None,
            )

            result = await parse_resume(resume_text, "C001")

        assert result["name"] == "范瑞杰"
        assert result["email"] == "2297734484@qq.com"
        assert result["phone"] == "+86 153-9764-7192"
        assert len(result["education"]) == 2
        assert result["education"][0]["school"] == "悉尼科技大学"
        assert result["education"][0]["degree"] == "硕士"
        assert result["education"][1]["school"] == "悉尼大学"
        assert result["education"][1]["degree"] == "学士"
        assert len(result["projects"]) == 4
        assert result["projects"][0]["name"] == "HireFlowAgents：AI 招聘辅助平台"
        assert len(result["work_experience"]) == 1
        assert result["work_experience"][0]["company"] == "四川 CA"
        assert "RAG" in result["skills"]
        assert "FastAPI" in result["skills"]
        assert all("{" not in skill and "}" not in skill for skill in result["skills"])
    asyncio.run(run())


def test_personal_summary_heading_is_not_candidate_name():
    """验证 PDF 开头的“个人概述”标题不会再覆盖候选人姓名。"""
    async def run():
        from app.agents.resume_agent import parse_resume
        from app.schemas.resume_schema import CandidateProfile

        resume_text = """个人概述
具备大模型应用开发经验，熟悉 LangGraph 和 RAG。
技能
Python、FastAPI
"""
        with patch("app.agents.resume_agent.call_llm_structured") as mock:
            mock.return_value = CandidateProfile(
                candidate_id="C001",
                name="个人概述",
                education=[],
                skills=["Python"],
                projects=[],
                work_experience=[],
                certifications=[],
                strengths=[],
                risks=[],
                missing_info=[],
            )
            result = await parse_resume(resume_text, "C001")

        assert result["name"] == ""

    asyncio.run(run())
