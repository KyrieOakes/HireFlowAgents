"""
tests/test_workflow.py
======================
验证 LangGraph 主流程能够复用数据库预解析状态、真正暂停并从同一 thread 恢复。

测试使用 InMemorySaver，不依赖本机 PostgreSQL；生产 API 仍使用 AsyncPostgresSaver。
"""

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

# 让单独运行此测试文件时也能从项目根目录导入 app 包。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.graph.workflow import build_workflow
from app.graph.nodes import ranking_agent_node
from app.api.workflow import (
    WorkflowRunRequest,
    _build_workflow_response,
    _prepare_initial_state,
)


def _initial_state() -> dict:
    """构造一个已经完成 JD 和简历解析的最小工作流状态。"""
    return {
        "job_id": "JOB-1",
        "jd_text": "Python 后端工程师",
        "jd_profile": {
            "job_title": "Python 后端工程师",
            "required_skills": ["Python"],
            "rubric": {},
        },
        "requested_limit": 5,
        "total_candidates": 1,
        "prescreened_count": 1,
        "resume_texts": [],
        "candidate_profiles": [
            {
                "candidate_id": "C-1",
                "name": "张三",
                "skills": ["Python"],
            }
        ],
        "resume_chunks": [],
        "retrieved_evidence": {},
        "evidence_agent_runs": [],
        "evidence_interventions": [],
        "evidence_review_status": "",
        "match_results": [],
        "ranking_results": {},
        "selected_candidate_ids": [],
        "interview_questions": {},
        "interview_feedback": {},
        "final_evaluations": {},
        "email_drafts": {},
        "human_review_status": "",
        "errors": [],
    }


def test_workflow_reuses_profiles_interrupts_and_resumes():
    """已有画像时跳过解析 Agent，并验证排名审核是 LangGraph 原生 interrupt。"""

    async def run_test():
        # InMemorySaver 保留 thread checkpoint，让测试可以执行真实 Command(resume=...)。
        workflow = build_workflow(InMemorySaver())
        config = {"configurable": {"thread_id": "workflow-test-thread"}}
        match_result = {
            "candidate_id": "C-1",
            "total_score": 88,
            "dimension_scores": {},
            "evidence": [],
            "strengths": ["Python 匹配"],
            "risks": [],
            "recommendation": "Strong Match",
            "summary": "匹配良好",
        }
        ranking_result = {
            "ranked_candidates": [match_result],
            "shortlist": ["C-1"],
            "explanation": "排名合理",
            "summary": {"total_candidates": 1},
        }

        with patch("app.graph.nodes.analyze_jd", new_callable=AsyncMock) as jd_mock, patch(
            "app.graph.nodes.parse_resume",
            new_callable=AsyncMock,
        ) as resume_mock, patch(
            "app.graph.nodes.batch_collect_evidence",
            new_callable=AsyncMock,
            return_value=({"C-1": []}, []),
        ), patch(
            "app.graph.nodes.batch_match_candidates",
            new_callable=AsyncMock,
            return_value=[match_result],
        ), patch(
            "app.graph.nodes.rank_candidates",
            new_callable=AsyncMock,
            return_value=ranking_result,
        ):
            paused = await workflow.ainvoke(_initial_state(), config)

            # 数据库画像已经存在，因此 JD Agent 和 Resume Agent 不应重复花费 LLM 调用。
            jd_mock.assert_not_awaited()
            resume_mock.assert_not_awaited()
            assert paused["ranking_results"]["shortlist"] == ["C-1"]
            assert paused["__interrupt__"][0].value["status"] == "pending_review"

            # 驳回属于正常人工动作：工作流重新评分后再次暂停，但不能污染 errors。
            reranked = await workflow.ainvoke(
                Command(resume={"action": "reject", "selected_candidate_ids": []}),
                config,
            )
            assert reranked["__interrupt__"][0].value["status"] == "pending_review"
            assert reranked["errors"] == []

            completed = await workflow.ainvoke(
                Command(
                    resume={
                        "action": "approve_shortlist",
                        "selected_candidate_ids": ["C-1"],
                    }
                ),
                config,
            )

        assert completed["human_review_status"] == "approved"
        assert completed["selected_candidate_ids"] == ["C-1"]
        assert "__interrupt__" not in completed

    asyncio.run(run_test())


def test_prepare_initial_state_reuses_database_profiles():
    """API 初始状态应复用数据库画像、合并 rubric，并保留 Top-N 限制。"""

    async def run_test():
        job = SimpleNamespace(
            job_id="JOB-1",
            jd_text="Python 后端工程师",
            jd_profile_json={"required_skills": ["Python"]},
            rubric_json={"technical_skills": 30},
        )
        candidate = SimpleNamespace(
            candidate_id="C-1",
            name="人工确认姓名",
            profile_json={"name": "旧姓名", "skills": ["Python"]},
            resume_text="Python 项目经历",
        )

        with patch("app.api.workflow.crud.get_job", return_value=job), patch(
            "app.api.workflow.crud.get_all_candidates",
            return_value=[candidate],
        ), patch(
            "app.api.workflow.pre_screen_candidates",
            return_value=[{"candidate_id": "C-1", "name": "人工确认姓名", "skills": ["Python"]}],
        ), patch(
            "app.api.workflow.ensure_candidate_indexes",
            new_callable=AsyncMock,
            return_value=0,
        ) as ensure_indexes:
            state = await _prepare_initial_state(
                WorkflowRunRequest(job_id="JOB-1", limit=5),
                db=SimpleNamespace(),
            )

        assert state["jd_profile"]["rubric"] == {"technical_skills": 30}
        assert state["candidate_profiles"][0]["name"] == "人工确认姓名"
        assert state["resume_texts"] == []
        assert state["requested_limit"] == 5
        ensure_indexes.assert_awaited_once()

    asyncio.run(run_test())


def test_prepare_initial_state_sends_full_recall_pool_to_langgraph():
    """Top 2 只能在精排后截断，初始状态必须保留完整的关键词召回池。"""

    async def run_test():
        job = SimpleNamespace(
            job_id="JOB-1",
            jd_text="Python 后端工程师",
            jd_profile_json={"required_skills": ["Python"]},
            rubric_json={},
        )
        candidates = [
            SimpleNamespace(
                candidate_id=f"C-{index}",
                name=f"候选人{index}",
                profile_json={"name": f"候选人{index}", "skills": ["Python"]},
                resume_text="Python 项目经历",
            )
            for index in range(1, 9)
        ]
        recalled_profiles = [
            {
                "candidate_id": candidate.candidate_id,
                "name": candidate.name,
                "skills": ["Python"],
            }
            for candidate in candidates
        ]

        with patch("app.api.workflow.crud.get_job", return_value=job), patch(
            "app.api.workflow.crud.get_all_candidates",
            return_value=candidates,
        ), patch(
            "app.api.workflow.pre_screen_candidates",
            return_value=recalled_profiles,
        ) as prescreen, patch(
            "app.api.workflow.ensure_candidate_indexes",
            new_callable=AsyncMock,
            return_value=0,
        ) as ensure_indexes:
            state = await _prepare_initial_state(
                WorkflowRunRequest(job_id="JOB-1", limit=2),
                db=SimpleNamespace(),
            )

        # 数据库只有 8 人，因此 max(2 * 3, 15) 会被收缩为 8 人召回池。
        assert prescreen.call_args.kwargs["top_k"] == 8
        assert state["prescreened_count"] == 8
        assert len(state["candidate_profiles"]) == 8
        assert len(ensure_indexes.await_args.args[0]) == 8

    asyncio.run(run_test())


def test_ranking_node_truncates_only_after_full_pool_is_scored():
    """Ranking 必须收到完整 Match 结果，完成排序后才返回用户要求的 Top 2。"""

    async def run_test():
        state = _initial_state()
        state["requested_limit"] = 2
        state["match_results"] = [
            {"candidate_id": "C-1", "total_score": 70},
            {"candidate_id": "C-2", "total_score": 92},
            {"candidate_id": "C-3", "total_score": 81},
        ]

        with patch(
            "app.agents.ranking_agent.call_llm_async",
            new_callable=AsyncMock,
            return_value="C-2 与 C-3 的综合匹配度最高",
        ):
            result = await ranking_agent_node(state)

        ranking = result["ranking_results"]
        assert [item["candidate_id"] for item in ranking["ranked_candidates"]] == ["C-2", "C-3"]
        assert ranking["shortlist"] == ["C-2", "C-3"]
        assert ranking["summary"]["evaluated_candidates"] == 3
        assert ranking["summary"]["returned_candidates"] == 2

    asyncio.run(run_test())


def test_workflow_response_exposes_pending_review_and_rank():
    """统一响应必须识别人工中断，并给候选人补前端需要的排名序号。"""
    values = _initial_state()
    values["match_results"] = [{"candidate_id": "C-1", "total_score": 88}]
    values["ranking_results"] = {
        "ranked_candidates": [{"candidate_id": "C-1", "total_score": 88}],
        "shortlist": ["C-1"],
    }

    response = _build_workflow_response(
        values=values,
        thread_id="thread-1",
        interrupt_payload={
            "status": "pending_review",
            "message": "请人工确认",
        },
    )

    assert response["status"] == "pending_review"
    assert response["ranking"]["ranked_candidates"][0]["rank"] == 1
    assert response["ranking"]["shortlist"] == ["C-1"]
    assert response["returned"] == 1
    assert response["thread_id"] == "thread-1"
