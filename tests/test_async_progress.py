"""
tests/test_async_progress.py
============================
验证后台匹配的真实进度事件，以及 Evidence/Match 的有界异步并发。

这些测试不调用真实模型、Qdrant 或 PostgreSQL，只检查事件协议、并发上限和结果顺序。
"""

import asyncio
from unittest.mock import patch
from uuid import uuid4

from app.agents.evidence_agent import batch_collect_evidence
from app.agents.match_agent import batch_match_candidates
from app.schemas.evidence_agent_schema import EvidenceAgentRun
from app.services.workflow_progress import (
    create_progress_tracker,
    finish_progress,
    iter_progress_events,
    publish_progress,
)


def test_progress_events_replay_until_final_result():
    """SSE 注册表必须回放真实阶段，并以唯一 result 事件结束。"""

    async def run_test():
        thread_id = f"progress-test-{uuid4().hex}"
        create_progress_tracker(thread_id, "JOB-1")
        await publish_progress(
            thread_id,
            phase="prescreening",
            message="关键词粗排完成，召回 15 人",
            completed=20,
            total=20,
        )
        await publish_progress(
            thread_id,
            phase="evidence",
            message="Evidence Agent 已完成 1/15",
            completed=1,
            total=15,
        )
        await finish_progress(
            thread_id,
            {
                "status": "pending_review",
                "message": "等待人工确认",
                "thread_id": thread_id,
            },
        )

        events = [event async for event in iter_progress_events(thread_id)]
        assert [event["sequence"] for event in events] == [1, 2, 3]
        assert [event["type"] for event in events] == ["progress", "progress", "result"]
        assert events[-1]["response"]["status"] == "pending_review"

    asyncio.run(run_test())


def test_evidence_batch_uses_bounded_concurrency_and_keeps_order():
    """Evidence 可以同时处理两人，但不能超限，最终顺序仍与粗排输入一致。"""

    async def run_test():
        active = 0
        max_active = 0
        progress_events = []
        active_lock = asyncio.Lock()

        async def fake_run_evidence_agent(*, jd_profile, candidate_profile, **kwargs):
            nonlocal active, max_active
            async with active_lock:
                active += 1
                max_active = max(max_active, active)
            await asyncio.sleep(0.01)
            async with active_lock:
                active -= 1
            return EvidenceAgentRun(
                candidate_id=candidate_profile["candidate_id"],
                status="completed",
                iterations=1,
                stop_reason="evidence_collected",
            )

        async def record_progress(**event):
            progress_events.append(event)

        profiles = [
            {"candidate_id": f"C-{index}", "name": f"候选人{index}"}
            for index in range(4)
        ]
        with patch(
            "app.agents.evidence_agent.run_evidence_agent",
            side_effect=fake_run_evidence_agent,
        ):
            _, runs = await batch_collect_evidence(
                jd_profile={"required_skills": ["Python"]},
                candidate_profiles=profiles,
                progress_callback=record_progress,
                max_concurrency=2,
            )

        assert max_active == 2
        assert [run.candidate_id for run in runs] == ["C-0", "C-1", "C-2", "C-3"]
        assert progress_events[-1]["status"] == "completed"
        assert progress_events[-1]["completed"] == 4

    asyncio.run(run_test())


def test_match_batch_uses_async_semaphore_and_keeps_order():
    """Match 使用 asyncio.Semaphore 并发评分，并按输入顺序返回结构化结果。"""

    async def run_test():
        active = 0
        max_active = 0
        progress_events = []
        active_lock = asyncio.Lock()

        async def fake_match_candidate(*, candidate_profile, **kwargs):
            nonlocal active, max_active
            async with active_lock:
                active += 1
                max_active = max(max_active, active)
            await asyncio.sleep(0.01)
            async with active_lock:
                active -= 1
            return {
                "candidate_id": candidate_profile["candidate_id"],
                "total_score": 80,
                "strengths": ["技术匹配"],
                "risks": [],
                "summary": "匹配结果稳定",
            }

        async def record_progress(**event):
            progress_events.append(event)

        profiles = [
            {"candidate_id": f"C-{index}", "name": f"候选人{index}"}
            for index in range(5)
        ]
        with patch(
            "app.agents.match_agent.match_candidate",
            side_effect=fake_match_candidate,
        ):
            results = await batch_match_candidates(
                jd_profile={"required_skills": ["Python"]},
                candidate_profiles=profiles,
                progress_callback=record_progress,
                max_concurrency=2,
            )

        assert max_active == 2
        assert [result["candidate_id"] for result in results] == [
            "C-0",
            "C-1",
            "C-2",
            "C-3",
            "C-4",
        ]
        assert progress_events[-1]["status"] == "completed"
        assert progress_events[-1]["completed"] == 5

    asyncio.run(run_test())
