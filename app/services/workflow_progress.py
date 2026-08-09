"""
app/services/workflow_progress.py
=================================
LangGraph 匹配任务的实时进度注册表。

当前开发版使用进程内内存保存短期事件，作用是把后台任务的真实阶段通过 SSE
推送给浏览器。正式多进程部署时可以把同一接口替换为 Redis Pub/Sub 或消息队列，
而 PostgreSQL LangGraph checkpoint 仍然负责保存可恢复的业务状态。
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional


# 结束状态表示后台任务已经运行到人工中断、正常结束或失败，SSE 可以安全关闭。
TERMINAL_PROGRESS_STATUSES = {
    "evidence_agent_needs_review",
    "pending_review",
    "completed",
    "failed",
}


@dataclass
class WorkflowProgressTracker:
    """保存一次匹配任务的事件历史、最终响应和等待条件。"""

    thread_id: str
    job_id: str
    status: str = "queued"
    events: List[Dict[str, Any]] = field(default_factory=list)
    response: Optional[Dict[str, Any]] = None
    created_at: float = field(default_factory=time.monotonic)
    # Condition 让 SSE 在没有新事件时休眠；发布事件后会立即唤醒所有订阅者。
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)


# 单进程开发服务器中的任务注册表。每次创建新任务时会清理较早的已结束记录。
_TRACKERS: Dict[str, WorkflowProgressTracker] = {}
_MAX_TRACKERS = 100


def create_progress_tracker(thread_id: str, job_id: str) -> WorkflowProgressTracker:
    """为一个新 thread_id 创建进度容器，并清理过期的已结束任务。"""
    if len(_TRACKERS) >= _MAX_TRACKERS:
        finished = [
            tracker
            for tracker in _TRACKERS.values()
            if tracker.status in TERMINAL_PROGRESS_STATUSES
        ]
        for tracker in sorted(finished, key=lambda item: item.created_at)[:20]:
            _TRACKERS.pop(tracker.thread_id, None)

    tracker = WorkflowProgressTracker(thread_id=thread_id, job_id=job_id)
    _TRACKERS[thread_id] = tracker
    return tracker


def get_progress_tracker(thread_id: str) -> Optional[WorkflowProgressTracker]:
    """读取任务进度；服务器重启后内存记录不存在时返回 None。"""
    return _TRACKERS.get(thread_id)


async def publish_progress(
    thread_id: str,
    *,
    phase: str,
    status: str = "running",
    message: str,
    completed: int = 0,
    total: int = 0,
    candidate_id: str = "",
    candidate_name: str = "",
) -> None:
    """写入一条真实进度事件，并唤醒正在等待的 SSE 客户端。"""
    tracker = _TRACKERS.get(thread_id)
    if not tracker:
        return

    async with tracker.condition:
        sequence = len(tracker.events) + 1
        # status 是“当前阶段”的 running/completed；整个任务在 finish_progress 前始终 running。
        tracker.status = "running"
        tracker.events.append(
            {
                "type": "progress",
                "sequence": sequence,
                "thread_id": thread_id,
                "phase": phase,
                "status": status,
                "message": message,
                "completed": completed,
                "total": total,
                "candidate_id": candidate_id,
                "candidate_name": candidate_name,
                "elapsed_seconds": round(time.monotonic() - tracker.created_at, 1),
            }
        )
        tracker.condition.notify_all()


async def finish_progress(
    thread_id: str,
    response: Dict[str, Any],
) -> None:
    """保存最终工作流响应并发布最后一条 result 事件。"""
    tracker = _TRACKERS.get(thread_id)
    if not tracker:
        return

    async with tracker.condition:
        tracker.status = str(response.get("status", "completed"))
        tracker.response = response
        tracker.events.append(
            {
                "type": "result",
                "sequence": len(tracker.events) + 1,
                "thread_id": thread_id,
                "status": tracker.status,
                "response": response,
                "elapsed_seconds": round(time.monotonic() - tracker.created_at, 1),
            }
        )
        tracker.condition.notify_all()


async def fail_progress(thread_id: str, message: str) -> Dict[str, Any]:
    """把后台未捕获异常转换为前端可读的失败响应。"""
    response = {
        "status": "failed",
        "message": message,
        "thread_id": thread_id,
        "ranking": {"ranked_candidates": [], "shortlist": []},
        "agent_runs": [],
        "interventions": [],
        "selected_candidate_ids": [],
        "errors": [message],
    }
    await finish_progress(thread_id, response)
    return response


async def iter_progress_events(
    thread_id: str,
    after_sequence: int = 0,
) -> AsyncIterator[Optional[Dict[str, Any]]]:
    """
    按顺序产出 SSE 事件；15 秒没有新事件时产出 None 作为心跳。

    after_sequence 允许重连客户端跳过已经收到的事件。当前浏览器第一次连接传 0，
    因此也能回放“POST 返回到 SSE 建连之间”产生的早期进度。
    """
    tracker = _TRACKERS.get(thread_id)
    if not tracker:
        return

    cursor = max(after_sequence, 0)
    while True:
        event: Optional[Dict[str, Any]] = None
        terminal_without_more_events = False

        async with tracker.condition:
            if cursor < len(tracker.events):
                event = tracker.events[cursor]
                cursor += 1
            elif tracker.status in TERMINAL_PROGRESS_STATUSES:
                terminal_without_more_events = True
            else:
                try:
                    await asyncio.wait_for(tracker.condition.wait(), timeout=15.0)
                except asyncio.TimeoutError:
                    # None 会由 API 转换成 SSE 注释心跳，不会触发前端业务事件。
                    event = None

        if terminal_without_more_events:
            break
        if event is not None:
            yield event
        else:
            yield None
