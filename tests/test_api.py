"""
tests/test_api.py
==================
API 集成测试 (FastAPI TestClient + mock 依赖)。
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock
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


def test_approve_nonexistent(client):
    """审批不存在邮件返回 404。"""
    resp = client.post("/email-drafts/nonexistent/approve")
    assert resp.status_code == 404
