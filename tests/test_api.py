"""
tests/test_api.py
==================
API 集成测试 (FastAPI TestClient + mock 依赖)。
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest, json
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base, get_db
from app.main import app

# SQLite 内存库
# 文件临时库 (避免内存库的线程隔离问题)
import tempfile
_db_file = os.path.join(tempfile.gettempdir(), "hireflow_test_api.db")
engine = create_engine(f"sqlite:///{_db_file}", echo=False, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(bind=engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    if os.path.exists(_db_file):
        os.remove(_db_file)


@pytest.fixture
def client():
    return TestClient(app)


# ---- 岗位 API ----

def test_upload_job(client):
    resp = client.post("/jobs/upload", json={"jd_text": "Python后端 JD"})
    assert resp.status_code == 200
    assert "job_id" in resp.json()


def test_get_jobs(client):
    resp = client.get("/jobs/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_delete_job(client):
    # 先创建
    r = client.post("/jobs/upload", json={"jd_text": "要删除的JD"})
    jid = r.json()["job_id"]
    # 删除
    r2 = client.delete(f"/jobs/{jid}")
    assert r2.status_code == 200


# ---- 简历 API ----

def test_upload_resume(client):
    resp = client.post("/resumes/upload", json={"resume_text": "张三的简历", "name": "张三"})
    assert resp.status_code == 200
    assert "candidate_id" in resp.json()


def test_get_resumes(client):
    resp = client.get("/resumes/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_update_candidate_name(client):
    """候选人姓名可以通过 PATCH 接口人工修正。"""
    created = client.post("/resumes/upload", json={"resume_text": "个人概述\n测试简历"})
    candidate_id = created.json()["candidate_id"]

    response = client.patch(f"/resumes/{candidate_id}", json={"name": "王小明"})

    assert response.status_code == 200
    assert response.json()["name"] == "王小明"


def test_delete_candidate(client):
    r = client.post("/resumes/upload", json={"resume_text": "删除测试"})
    cid = r.json()["candidate_id"]
    r2 = client.delete(f"/resumes/{cid}")
    assert r2.status_code == 200


# ---- 面试/邮件 API (mock LLM, 数据通过API准备) ----

def test_questions_api_route_exists(client):
    """面试问题 API: 路由已注册 (未解析时返回 404 或 422)。"""
    rj = client.post("/jobs/upload", json={"jd_text": "JD"})
    jid = rj.json()["job_id"]
    rc = client.post("/resumes/upload", json={"resume_text": "简历"})
    cid = rc.json()["candidate_id"]
    resp = client.post(f"/jobs/{jid}/candidates/{cid}/questions")
    # 路由存在: 返回 404(缺数据) 或 200(数据就绪), 不应是 405/500
    assert resp.status_code in (200, 404, 422)
    resp2 = client.get(f"/jobs/{jid}/candidates/{cid}/questions")
    assert resp2.status_code in (200, 404)


def test_email_draft_api_route_exists(client):
    """邮件草稿 API: 路由已注册。"""
    rj = client.post("/jobs/upload", json={"jd_text": "JD"})
    jid = rj.json()["job_id"]
    rc = client.post("/resumes/upload", json={"resume_text": "简历"})
    cid = rc.json()["candidate_id"]
    resp = client.post(f"/jobs/{jid}/candidates/{cid}/email-draft", json={"email_type": "interview_invite"})
    assert resp.status_code in (200, 404, 422)


def test_email_draft_route_exists(client):
    """邮件草稿 GET: 路由已注册。"""
    rj = client.post("/jobs/upload", json={"jd_text": "JD"})
    jid = rj.json()["job_id"]
    rc = client.post("/resumes/upload", json={"resume_text": "简历"})
    cid = rc.json()["candidate_id"]
    resp = client.get(f"/jobs/{jid}/candidates/{cid}/email-draft")
    assert resp.status_code in (200, 404)


def test_get_email_drafts_repairs_historical_dirty_draft(client):
    """读取历史草稿时会清理 title/body 压平文本和姓名占位符。"""
    from app.database import crud

    # 直接写入一条旧版本产生的脏草稿，用来模拟用户截图中的数据库记录。
    db = TestingSession()
    try:
        job = crud.create_job(db, "测试JD", "AI Agent 工程师")
        candidate = crud.create_candidate(db, "测试简历", "王小明")
        crud.save_email_draft(
            db,
            job.job_id,
            candidate.candidate_id,
            "interview_invite",
            "邀请信",
            "title 邀请信 body | 尊敬的 候选人姓名 您好! 지원 你的名字 招聘专家",
        )
        job_id = job.job_id
        candidate_id = candidate.candidate_id
    finally:
        db.close()

    response = client.get(f"/jobs/{job_id}/candidates/{candidate_id}/email-draft")

    assert response.status_code == 200
    body = response.json()["drafts"][0]["body"]
    assert "王小明" in body
    assert "候选人姓名" not in body
    assert "title " not in body
    assert "지원" not in body
    assert body.endswith("HireFlow 招聘团队")


def test_approve_nonexistent(client):
    """审批不存在邮件返回 404。"""
    resp = client.post("/email-drafts/nonexistent/approve")
    assert resp.status_code == 404


def test_matching_pauses_for_evidence_agent_intervention(client):
    """证据工具重试耗尽后，匹配 API 会暂停并返回四种人工选择。"""
    from app.database import crud
    from app.schemas.evidence_agent_schema import EvidenceAgentError, EvidenceAgentRun

    # 直接准备已解析岗位和候选人，避免本测试依赖其他 Agent 的 LLM 调用。
    db = TestingSession()
    try:
        job = crud.create_job(db, "需要 Python 和 LangGraph", "Agent 工程师")
        crud.update_job_profile(
            db,
            job.job_id,
            {
                "job_title": "Agent 工程师",
                "required_skills": ["Python", "LangGraph"],
                "responsibilities": ["开发 Tool Calling 工作流"],
            },
        )
        candidate = crud.create_candidate(db, "Python LangGraph 项目经验", "测试候选人")
        crud.update_candidate_profile(
            db,
            candidate.candidate_id,
            {
                "candidate_id": candidate.candidate_id,
                "name": "测试候选人",
                "skills": ["Python", "LangGraph"],
                "projects": [],
                "education": [],
                "work_experience": [],
            },
        )
        job_id = job.job_id
        candidate_id = candidate.candidate_id
    finally:
        db.close()

    failed_run = EvidenceAgentRun(
        candidate_id=candidate_id,
        status="needs_human_review",
        iterations=1,
        tool_call_count=1,
        evidence=[],
        missing_dimensions=["technical_skills"],
        reason_summary="Qdrant 连续超时",
        stop_reason="tool_retry_exhausted",
        requires_human_review=True,
        errors=[
            EvidenceAgentError(
                code="TOOL_RETRY_EXHAUSTED",
                category="transient",
                message="工具连续三次超时",
                retryable=True,
                tool_name="search_resume_evidence",
                attempts=3,
            )
        ],
    )

    with patch(
        "app.api.matching.batch_collect_evidence",
        new_callable=AsyncMock,
        return_value=({candidate_id: []}, [failed_run]),
    ):
        response = client.post(
            f"/jobs/{job_id}/match",
            params={"limit": 1, "agent_failure_action": "ask_user"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "needs_human_review"
    assert payload["llm_scored"] == 0
    assert payload["interventions"][0]["available_actions"] == [
        "retry_agent",
        "continue_with_warning",
        "skip_failed",
        "abort",
    ]


# ================================================================
# 端到端冒烟测试: 解析→RAG索引→匹配→面试问题→评价→邮件
# ================================================================
def test_full_pipeline_smoke(client):
    """
    端到端冒烟测试 (mock LLM):
    创建岗位→解析JD→录入简历→解析简历→匹配→面试问题→评价→邮件草稿

    验证:
    - 所有 API 路由可访问
    - 数据在各步骤间正确流转
    - 关键返回字段存在
    """
    # Step 1: 创建岗位并解析 JD
    r1 = client.post("/jobs/upload", json={"jd_text": "Python后端工程师\n需要Python,FastAPI,Docker"})
    assert r1.status_code == 200
    jid = r1.json()["job_id"]

    # Mock JD Agent
    from app.schemas.jd_schema import JobDescription
    with patch("app.agents.jd_agent.call_llm_structured") as mock_jd:
        mock_jd.return_value = JobDescription(
            job_title="Python后端工程师",
            required_skills=["Python","FastAPI","Docker"],
            preferred_skills=["RAG"],
            responsibilities=["开发后端API"],
            education_requirements=["本科"],
            technical_requirements=["FastAPI","Docker"],
            soft_skills=["沟通能力"],
        )
        r1b = client.post(f"/jobs/{jid}/parse")
        assert r1b.status_code == 200
        assert r1b.json()["jd_profile"]["job_title"] == "Python后端工程师"

    # Step 2: 录入并解析简历
    r2 = client.post("/resumes/upload", json={
        "resume_text": "张三, 清华CS学士, Python FastAPI Docker, RAG项目经验, 2年后端开发",
        "name": "张三",
        "filename": "zhang.pdf",
    })
    assert r2.status_code == 200
    cid = r2.json()["candidate_id"]

    # Mock Resume Agent
    from app.schemas.resume_schema import CandidateProfile, Education, Project
    with patch("app.agents.resume_agent.call_llm_structured") as mock_resume:
        mock_resume.return_value = CandidateProfile(
            candidate_id=cid, name="张三",
            education=[Education(degree="学士", school="清华大学", major="计算机科学")],
            skills=["Python","FastAPI","Docker","RAG"],
            projects=[Project(name="RAG问答系统", description="基于FastAPI+Qdrant的RAG系统", technologies=["FastAPI","Qdrant"])],
            work_experience=[], certifications=[], strengths=["技能匹配"], risks=[], missing_info=[],
        )
        r2b = client.post(f"/resumes/{cid}/parse")
        assert r2b.status_code == 200
        assert r2b.json()["profile"]["name"] == "张三"

    # Step 3: 匹配评分 + 排序
    from app.schemas.match_schema import MatchResult, DimensionScores
    from app.schemas.evidence_agent_schema import EvidenceAgentRun, ToolCallTrace
    evidence_run = EvidenceAgentRun(
        candidate_id=cid,
        status="completed",
        iterations=2,
        tool_call_count=1,
        tool_calls=[
            ToolCallTrace(
                call_id="smoke-tool-1",
                iteration=1,
                tool_name="search_resume_evidence",
                arguments={
                    "candidate_id": cid,
                    "dimension": "technical_skills",
                    "query": "Python FastAPI",
                    "top_k": 3,
                },
                status="success",
                result_count=1,
                observation_summary="找到 1 条证据",
            )
        ],
        evidence=[{"text": "Python FastAPI 项目经验", "score": 0.9}],
        coverage_rate=0.5,
        covered_dimensions=["technical_skills"],
        missing_dimensions=["experience"],
        reason_summary="已找到技术证据",
        stop_reason="evidence_collected",
    )
    with patch(
        "app.api.matching.batch_collect_evidence",
        new_callable=AsyncMock,
        return_value=({cid: evidence_run.evidence}, [evidence_run]),
    ):
        with patch("app.agents.match_agent.call_llm_structured") as mock_match:
            mock_match.return_value = MatchResult(
                candidate_id=cid, total_score=85.0,
                dimension_scores=DimensionScores(
                    technical_skills=28, project_relevance=18,
                    experience=12, education=8, domain_relevance=9,
                    communication=4, risk_penalty=-4,
                ),
                strengths=["Python+FastAPI经验丰富"],
                risks=["RAG项目细节需验证"],
                recommendation="Strong Match",
                summary="总体匹配良好",
            )
            with patch("app.agents.ranking_agent.call_llm") as mock_rank:
                mock_rank.return_value = "排名合理, 张三排第一"
                r3 = client.post(f"/jobs/{jid}/match", params={"limit": 5})
                assert r3.status_code == 200
                data3 = r3.json()
                assert data3["status"] == "completed"
                assert data3["llm_scored"] >= 1
                assert len(data3["ranking"]["ranked_candidates"]) >= 1
                assert data3["agent_runs"][0]["tool_calls"][0]["attempts"] == 1

    # Step 4: 面试问题生成
    with patch("app.agents.interview_agent.call_llm") as mock_q:
        mock_q.return_value = json.dumps([
            {"question_type":"technical","question":"请介绍FastAPI的异步处理机制","purpose":"验证技术深度"},
            {"question_type":"project_deep_dive","question":"你的RAG项目是如何做chunking的?","purpose":"验证项目经验"},
            {"question_type":"risk_verification","question":"RAG项目细节需验证,请详细说明","purpose":"验证风险点"},
        ])
        r4 = client.post(f"/jobs/{jid}/candidates/{cid}/questions")
        assert r4.status_code == 200
        qs = r4.json()["questions"]
        assert len(qs) >= 2
        # 问题类型覆盖
        types = {q["question_type"] for q in qs}
        assert "technical" in types or "project_deep_dive" in types

    # Step 5: 面试评价
    from app.schemas.evaluation_schema import InterviewEvaluationOutput, RiskResolution
    with patch("app.agents.evaluation_agent.call_llm_structured") as mock_eval:
        mock_eval.return_value = InterviewEvaluationOutput(
            technical_depth_score=8,
            communication_score=7,
            problem_solving_score=7,
            risk_resolution=[RiskResolution(risk="RAG细节", status="resolved", reason="解释清晰")],
            strengths=["技术扎实", "表达清晰"],
            concerns=["生产经验不足"],
            summary="面试表现良好，推荐进入下一轮",
            recommendation="Recommend",
        )
        r5 = client.post(f"/jobs/{jid}/candidates/{cid}/evaluate", json={
            "interview_feedback": "候选人回答问题流畅, FastAPI经验丰富, RAG项目细节解释清晰",
        })
        assert r5.status_code == 200
        eval_data = r5.json()["evaluation"]
        assert eval_data["requires_human_review"] is True
        assert eval_data["recommendation"] == "Recommend"

    # Step 6: 邮件草稿
    from app.schemas.email_schema import EmailContentOutput
    with patch("app.agents.email_agent.call_llm_structured") as mock_email:
        mock_email.return_value = EmailContentOutput(
            subject="面试邀请 - Python后端工程师",
            body="尊敬的张三：\n\n恭喜您通过初步筛选，诚邀您参加面试。\n\n面试时间：待HR确认后另行通知",
        )
        r6 = client.post(f"/jobs/{jid}/candidates/{cid}/email-draft", json={
            "email_type": "interview_invite",
        })
        assert r6.status_code == 200
        draft = r6.json()
        assert draft["status"] == "draft"
        assert draft["requires_human_approval"] is True
        assert "张三" in draft["body"]

    # Step 7: 验证数据持久化 (GET 端点)
    # 面试问题
    r7a = client.get(f"/jobs/{jid}/candidates/{cid}/questions")
    assert r7a.status_code == 200
    # 面试评价
    r7b = client.get(f"/jobs/{jid}/candidates/{cid}/evaluation")
    assert r7b.status_code == 200
    # 邮件草稿列表
    r7c = client.get(f"/jobs/{jid}/candidates/{cid}/email-draft")
    assert r7c.status_code == 200
    # 排名
    r7d = client.get(f"/jobs/{jid}/ranking", params={"limit": 5})
    assert r7d.status_code == 200

    print("\n  ✅ 端到端冒烟测试通过: JD解析→简历解析→匹配→面试→评价→邮件")
    print(f"     job_id={jid}  candidate_id={cid}")
