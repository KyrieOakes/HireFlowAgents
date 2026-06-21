"""
tests/test_crud.py
==================
CRUD 集成测试 (SQLite 内存库, 无需 PostgreSQL)。
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.database.models import Base
from app.database import crud


@pytest.fixture(scope="module")
def engine():
    """创建 SQLite 内存数据库引擎 (module级别, 复用)。"""
    return create_engine("sqlite:///:memory:", echo=False)


@pytest.fixture(scope="module")
def create_tables(engine):
    """建表 (module级别, 只执行一次)。"""
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db(engine, create_tables):
    """每个测试独立的数据库会话 (事务回滚)。"""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


# ---- 岗位 CRUD ----

def test_create_and_get_job(db: Session):
    job = crud.create_job(db, "测试JD文本", "测试岗位")
    assert job.job_id is not None
    assert job.title == "测试岗位"

    fetched = crud.get_job(db, job.job_id)
    assert fetched is not None
    assert fetched.jd_text == "测试JD文本"


def test_update_job_profile(db: Session):
    job = crud.create_job(db, "JD文本")
    profile = {"job_title": "Python后端", "required_skills": ["Python"]}
    updated = crud.update_job_profile(db, job.job_id, profile)
    assert updated.title == "Python后端"
    assert updated.jd_profile_json == profile


def test_delete_job(db: Session):
    job = crud.create_job(db, "JD文本")
    assert crud.delete_job(db, job.job_id) is True
    assert crud.get_job(db, job.job_id) is None


# ---- 候选人 CRUD ----

def test_create_and_get_candidate(db: Session):
    c = crud.create_candidate(db, "简历文本", "张三", "z@test.com", "resume.pdf")
    assert c.candidate_id is not None
    assert c.name == "张三"
    fetched = crud.get_candidate(db, c.candidate_id)
    assert fetched.resume_text == "简历文本"


def test_update_candidate_profile(db: Session):
    c = crud.create_candidate(db, "简历文本", "张三")
    profile = {"name": "张三丰", "skills": ["Python"]}
    updated = crud.update_candidate_profile(db, c.candidate_id, profile)
    assert updated.name == "张三丰"


def test_auto_named_protection(db: Session):
    """自动命名"申请人X"被保护, LLM 提取的空名/申请人模式不覆盖。"""
    c = crud.create_candidate(db, "简历文本", "申请人A")
    # LLM 提取到空名 → 保持自动命名
    profile = {"name": "", "skills": []}
    crud.update_candidate_profile(db, c.candidate_id, profile)
    fetched = crud.get_candidate(db, c.candidate_id)
    assert fetched.name == "申请人A"  # 空名不覆盖


def test_delete_candidate(db: Session):
    c = crud.create_candidate(db, "简历文本")
    assert crud.delete_candidate(db, c.candidate_id) is True
    assert crud.get_candidate(db, c.candidate_id) is None


# ---- 匹配结果 CRUD ----

def test_save_match_result(db: Session):
    job = crud.create_job(db, "JD")
    c = crud.create_candidate(db, "简历")
    m = crud.save_match_result(
        db, job.job_id, c.candidate_id, 85.0,
        {"tech": 28}, [], [], [], "Strong Match",
    )
    assert m.total_score == 85.0
    results = crud.get_match_results_by_job(db, job.job_id)
    assert len(results) == 1


# ---- 邮件草稿 CRUD ----

def test_email_draft_flow(db: Session):
    job = crud.create_job(db, "JD")
    c = crud.create_candidate(db, "简历")
    draft = crud.save_email_draft(db, job.job_id, c.candidate_id, "interview_invite", "面试邀请", "尊敬的张三...")
    assert draft.status == "draft"

    drafts = crud.get_email_drafts(db, job.job_id, c.candidate_id)
    assert len(drafts) == 1

    approved = crud.approve_email_draft(db, draft.email_id)
    assert approved.status == "approved"
