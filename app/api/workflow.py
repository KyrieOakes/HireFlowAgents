"""
app/api/workflow.py
====================
LangGraph 招聘筛选主流程 API。

POST /workflow/run                 → 创建后台匹配任务并立即返回 thread_id
GET  /workflow/{thread_id}/events  → 通过 SSE 推送真实执行进度和最终结果
POST /workflow/{thread_id}/resume  → 提交人工决定并从 checkpoint 恢复
GET  /workflow/{thread_id}/state   → 读取持久化状态，支持刷新页面后恢复
"""

import asyncio
import json
from typing import Any, Dict, List, Literal
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import crud
from app.database.session import SessionLocal, get_db
from app.graph.state import HiringState
from app.services.matching_service import ensure_candidate_indexes
from app.services.pre_screening import pre_screen_candidates
from app.services.workflow_progress import (
    create_progress_tracker,
    fail_progress,
    finish_progress,
    get_progress_tracker,
    iter_progress_events,
    publish_progress,
)


router = APIRouter(prefix="/workflow", tags=["workflow"])


# ================================================================
# 请求模型
# ================================================================

class WorkflowRunRequest(BaseModel):
    """
    启动数据库岗位筛选工作流的请求。

    前端只传岗位 ID 和人数限制；后端会从 PostgreSQL 读取已经解析好的
    JD 与候选人画像，避免把大段原始文本来回传输，也避免重复调用解析 Agent。
    """

    job_id: str
    limit: int = Field(default=0, ge=0)


class ResumeRequest(BaseModel):
    """恢复工作流时提交的人工决定。"""

    # 排名审核动作: approve_shortlist / reject / modify
    # 证据介入动作: retry_agent / continue_with_warning / skip_failed / abort
    action: Literal[
        "approve_shortlist",
        "reject",
        "modify",
        "retry_agent",
        "continue_with_warning",
        "skip_failed",
        "abort",
    ] = "approve_shortlist"
    selected_candidate_ids: List[str] = Field(default_factory=list)
    comment: str = ""


# ================================================================
# 初始状态与结果持久化
# ================================================================

async def _prepare_initial_state(
    request: WorkflowRunRequest,
    db: Session,
    progress_run_id: str = "",
) -> HiringState:
    """
    从业务数据库构建 LangGraph 初始状态。

    输入:
        request: 前端选择的岗位 ID 和 Top-N 人数。
        db: 当前 FastAPI 请求使用的 SQLAlchemy 会话。
    输出:
        HiringState: 已复用结构化 JD、完成粗筛并检查向量索引的初始状态。
    """
    # 第一步读取岗位；LangGraph 只接收已由用户完成解析的岗位。
    if progress_run_id:
        await publish_progress(
            progress_run_id,
            phase="loading",
            message="正在从 PostgreSQL 读取岗位和候选人",
        )
    job = crud.get_job(db, request.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在")
    if not job.jd_profile_json:
        raise HTTPException(status_code=400, detail="岗位尚未解析，请先解析岗位")

    # 第二步读取已经解析的候选人；未解析简历不会进入自动招聘判断。
    candidate_records = [candidate for candidate in crud.get_all_candidates(db) if candidate.profile_json]
    if not candidate_records:
        raise HTTPException(status_code=400, detail="没有已解析的候选人，请先解析简历")

    # profile_json 需要复制后再补 candidate_id，避免原地修改 SQLAlchemy JSON 字段。
    all_profiles: List[Dict[str, Any]] = []
    records_by_id: Dict[str, Any] = {}
    for candidate in candidate_records:
        profile = dict(candidate.profile_json)
        profile["candidate_id"] = candidate.candidate_id
        # 数据库顶层姓名是人工可修改的权威值，优先于旧画像里的姓名。
        profile["name"] = candidate.name or profile.get("name")
        all_profiles.append(profile)
        records_by_id[candidate.candidate_id] = candidate

    # 关键词阶段只负责低成本召回，不在这里提前截成用户要求的 Top-N。
    # 例如用户选择 Top 5 时，先召回 max(5 * 3, 15) = 15 人；这 15 人都要进入
    # Evidence Agent 和 Match Agent，最后由 Ranking Agent 根据模型评分截取 Top 5。
    if progress_run_id:
        await publish_progress(
            progress_run_id,
            phase="prescreening",
            message=f"正在对 {len(all_profiles)} 名候选人执行关键词粗排",
            total=len(all_profiles),
        )

    pool_size = (
        max(request.limit * 3, 15)
        if request.limit > 0
        else len(all_profiles)
    )
    pool_size = min(pool_size, len(all_profiles))
    prescreened_profiles = pre_screen_candidates(
        jd_profile=job.jd_profile_json,
        candidates=all_profiles,
        top_k=pool_size,
    )

    if progress_run_id:
        await publish_progress(
            progress_run_id,
            phase="prescreening",
            status="completed",
            message=f"关键词粗排完成，召回 {len(prescreened_profiles)} 人",
            completed=len(all_profiles),
            total=len(all_profiles),
        )

    # Evidence Agent 会处理整个召回池，因此这里也必须检查整个召回池的 Qdrant 索引。
    # 如果只检查最终 Top-N，就会再次退化成“关键词先决定结果、模型只做补充说明”。
    async def report_index_progress(**event: Any) -> None:
        """把索引检查的候选人级进度转发到当前 thread 的 SSE 事件流。"""
        if progress_run_id:
            await publish_progress(progress_run_id, phase="indexing", **event)

    await ensure_candidate_indexes(
        prescreened_profiles,
        records_by_id,
        db,
        progress_callback=report_index_progress if progress_run_id else None,
    )

    # Match Agent 从 jd_profile.rubric 读取评分规则，因此把数据库独立列合并进状态副本。
    jd_profile = dict(job.jd_profile_json)
    if job.rubric_json:
        jd_profile["rubric"] = job.rubric_json

    return {
        "job_id": request.job_id,
        "progress_run_id": progress_run_id,
        "jd_text": job.jd_text,
        "jd_profile": jd_profile,
        "requested_limit": request.limit,
        "total_candidates": len(all_profiles),
        "prescreened_count": len(prescreened_profiles),
        # 已有结构化画像，Resume Agent 节点会识别并跳过重复解析。
        "resume_texts": [],
        # 整个关键词召回池进入 LangGraph，真正参与证据检索和 LLM 多维评分。
        "candidate_profiles": prescreened_profiles,
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


def _as_dict(value: Any) -> Dict[str, Any]:
    """把 Pydantic 模型或普通字典统一转换成可保存的字典。"""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return dict(value)
    return {}


def _save_match_results(db: Session, values: Dict[str, Any]) -> None:
    """
    把 LangGraph 的 Match Agent 输出写入业务数据库。

    checkpoint 负责保存工作流进度；match_results 表负责给候选人详情、面试问题和
    邮件功能提供正式业务数据。两者用途不同，因此成功评分后必须同时保存。
    """
    job_id = str(values.get("job_id", ""))
    if not job_id:
        return

    for raw_result in values.get("match_results", []):
        result = _as_dict(raw_result)
        if not result.get("candidate_id"):
            continue
        dimension_scores = result.get("dimension_scores", {})
        crud.save_match_result(
            db=db,
            job_id=job_id,
            candidate_id=result["candidate_id"],
            total_score=result.get("total_score", 0),
            dimension_scores=_as_dict(dimension_scores),
            evidence=result.get("evidence", []),
            risks=result.get("risks", []),
            strengths=result.get("strengths", []),
            recommendation=result.get("recommendation", ""),
            summary=result.get("summary", ""),
        )


# ================================================================
# LangGraph interrupt 与统一响应
# ================================================================

def _extract_interrupt_payload(result: Dict[str, Any]) -> Dict[str, Any]:
    """从 ``ainvoke`` 返回值中的 LangGraph Interrupt 对象提取前端载荷。"""
    for interrupt_item in result.get("__interrupt__", []):
        value = getattr(interrupt_item, "value", None)
        if isinstance(value, dict):
            return value
        if isinstance(interrupt_item, dict) and isinstance(interrupt_item.get("value"), dict):
            return interrupt_item["value"]
    return {}


def _extract_snapshot_interrupt(snapshot: Any) -> Dict[str, Any]:
    """从持久化 StateSnapshot 的任务列表读取尚未处理的 interrupt 载荷。"""
    for task in getattr(snapshot, "tasks", ()):
        for interrupt_item in getattr(task, "interrupts", ()):
            value = getattr(interrupt_item, "value", None)
            if isinstance(value, dict):
                return value
    return {}


def _ranking_for_frontend(values: Dict[str, Any]) -> Dict[str, Any]:
    """给排序结果补上从 1 开始的 rank 字段，直接满足前端卡片契约。"""
    raw_ranking = values.get("ranking_results", {})
    ranking = _as_dict(raw_ranking)
    ranked_candidates = []
    for index, raw_candidate in enumerate(ranking.get("ranked_candidates", [])):
        candidate = _as_dict(raw_candidate)
        candidate["rank"] = index + 1
        ranked_candidates.append(candidate)
    return {
        **ranking,
        "ranked_candidates": ranked_candidates,
        "shortlist": list(ranking.get("shortlist", [])),
    }


def _build_workflow_response(
    values: Dict[str, Any],
    thread_id: str,
    interrupt_payload: Dict[str, Any] | None = None,
    next_steps: List[str] | None = None,
) -> Dict[str, Any]:
    """把启动、恢复和状态查询统一成同一种前端响应结构。"""
    payload = interrupt_payload or {}
    interrupt_status = str(payload.get("status", ""))
    human_status = str(values.get("human_review_status", ""))
    errors = list(values.get("errors", []))

    # interrupt 的载荷最准确：它能区分证据故障审核和最终排名审核。
    if interrupt_status in {"evidence_agent_needs_review", "pending_review"}:
        status = interrupt_status
    elif errors and human_status not in {"approved", "modified"}:
        status = "failed"
    elif human_status in {"approved", "modified"}:
        status = "completed"
    elif values.get("ranking_results"):
        # 兼容旧 checkpoint：即使旧版本没有保存 interrupt 载荷，有排名也必须人工确认。
        status = "pending_review"
    else:
        status = "completed"

    messages = {
        "evidence_agent_needs_review": "证据 Agent 已暂停，请选择后续处理方式",
        "pending_review": "候选人排名已生成，请人工确认面试名单",
        "completed": "人工审核已完成，工作流已结束",
        "failed": "工作流已结束，请根据错误信息处理后重新运行",
    }

    ranking = _ranking_for_frontend(values)

    return {
        "status": status,
        "message": str(payload.get("message") or messages[status]),
        "thread_id": thread_id,
        "job_id": values.get("job_id", ""),
        "limit": values.get("requested_limit", 0),
        "total_in_db": values.get("total_candidates", 0),
        "prescreened": values.get("prescreened_count", 0),
        "llm_scored": len(values.get("match_results", [])),
        "returned": len(ranking.get("ranked_candidates", [])),
        "ranking": ranking,
        "match_results": values.get("match_results", []),
        "agent_runs": values.get("evidence_agent_runs", []),
        # 处理完成后不再把旧干预项渲染成可点击按钮；完整失败轨迹仍保留在 agent_runs。
        "interventions": (
            values.get("evidence_interventions", [])
            if status == "evidence_agent_needs_review"
            else []
        ),
        "selected_candidate_ids": values.get("selected_candidate_ids", []),
        "human_review_status": human_status,
        "errors": errors,
        "next_steps": next_steps or [],
    }


# ================================================================
# API 路由
# ================================================================

async def _execute_workflow_run(
    thread_id: str,
    request: WorkflowRunRequest,
) -> None:
    """
    在后台执行完整 LangGraph，最终结果通过进度注册表交给 SSE。

    请求级 SQLAlchemy Session 在 POST 返回后会关闭，因此后台任务必须创建并关闭
    自己的 Session，不能复用 FastAPI Depends 注入的对象。
    """
    from app.graph.workflow import open_workflow

    db = SessionLocal()
    thread_config = {"configurable": {"thread_id": thread_id}}
    try:
        initial_state = await _prepare_initial_state(
            request,
            db,
            progress_run_id=thread_id,
        )
        async with open_workflow() as workflow:
            result = await workflow.ainvoke(initial_state, thread_config)
        _save_match_results(db, result)
        response = _build_workflow_response(
            values=result,
            thread_id=thread_id,
            interrupt_payload=_extract_interrupt_payload(result),
        )
        await finish_progress(thread_id, response)
    except HTTPException as exc:
        await fail_progress(thread_id, str(exc.detail))
    except asyncio.CancelledError:
        await fail_progress(thread_id, "匹配任务因服务关闭而中止，可从 checkpoint 检查进度后重试")
        raise
    except Exception as exc:
        # SSE 只返回可操作的上层信息；底层服务地址和密钥不能直接暴露给浏览器。
        await fail_progress(thread_id, f"工作流执行失败: {str(exc)}")
    finally:
        db.close()


@router.post("/run", status_code=202)
async def run_workflow(
    request: WorkflowRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """创建后台筛选任务并立即返回 thread_id，避免浏览器空等长请求。"""

    # 在返回 202 前完成低成本前置校验，让明显输入错误继续使用标准 HTTP 状态码。
    job = crud.get_job(db, request.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在")
    if not job.jd_profile_json:
        raise HTTPException(status_code=400, detail="岗位尚未解析，请先解析岗位")
    if not any(candidate.profile_json for candidate in crud.get_all_candidates(db)):
        raise HTTPException(status_code=400, detail="没有已解析的候选人，请先解析简历")

    # 每次运行都生成唯一线程，避免多个岗位或浏览器会话共享 checkpoint。
    thread_id = f"hireflow-{request.job_id}-{uuid4().hex}"
    create_progress_tracker(thread_id, request.job_id)
    # Starlette 会先把 202 响应发送给浏览器，再在应用事件循环中执行异步后台任务。
    # 相比裸 asyncio.create_task，这种方式会由框架持有任务生命周期和异常边界。
    background_tasks.add_task(
        _execute_workflow_run,
        thread_id,
        request.model_copy(deep=True),
    )

    return {
        "status": "queued",
        "message": "匹配任务已创建，正在等待后端执行",
        "thread_id": thread_id,
        "job_id": request.job_id,
        "limit": request.limit,
    }


@router.get("/{thread_id}/events")
async def stream_workflow_events(
    thread_id: str,
    after_sequence: int = 0,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    """通过 Server-Sent Events 回放并持续推送某次匹配的真实进度。"""
    if not get_progress_tracker(thread_id):
        raise HTTPException(status_code=404, detail="没有找到该任务的实时进度")

    # 浏览器自动重连 EventSource 时会发送 Last-Event-ID，避免从头重复渲染事件。
    resume_sequence = after_sequence
    if last_event_id and last_event_id.isdigit():
        resume_sequence = max(resume_sequence, int(last_event_id))

    async def event_stream():
        async for event in iter_progress_events(thread_id, resume_sequence):
            if event is None:
                # SSE 注释是标准心跳格式，不会触发前端 message 回调。
                yield ": keep-alive\n\n"
                continue
            payload = json.dumps(jsonable_encoder(event), ensure_ascii=False)
            yield f"id: {event.get('sequence', 0)}\ndata: {payload}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{thread_id}/resume", status_code=202)
async def resume_workflow(
    thread_id: str,
    request: ResumeRequest,
    background_tasks: BackgroundTasks,
):
    """校验 checkpoint 后立即返回，再在后台执行 ``Command(resume=...)``。"""
    from app.graph.workflow import open_workflow

    thread_config = {"configurable": {"thread_id": thread_id}}
    try:
        async with open_workflow() as workflow:
            # 这里只读取一次 checkpoint 做快速校验，真正恢复动作交给后台任务。
            snapshot = await workflow.aget_state(thread_config)
            if not snapshot.values:
                raise HTTPException(status_code=404, detail="没有找到该工作流")
            job_id = str(snapshot.values.get("job_id", ""))

        # 覆盖旧的已结束进度流；PostgreSQL checkpoint 本身不会被删除。
        create_progress_tracker(thread_id, job_id)
        background_tasks.add_task(
            _execute_workflow_resume,
            thread_id,
            request.model_copy(deep=True),
        )
        return {
            "status": "queued",
            "message": "人工决定已提交，正在从 checkpoint 恢复",
            "thread_id": thread_id,
            "job_id": job_id,
            "limit": int(snapshot.values.get("requested_limit", 0)),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"恢复工作流失败: {str(exc)}") from exc


async def _execute_workflow_resume(thread_id: str, request: ResumeRequest) -> None:
    """在后台执行人工恢复动作，并把重试、重排或完成进度继续推送到同一 SSE。"""
    from langgraph.types import Command
    from app.graph.workflow import open_workflow

    db = SessionLocal()
    thread_config = {"configurable": {"thread_id": thread_id}}
    human_input = {
        "action": request.action,
        "selected_candidate_ids": request.selected_candidate_ids,
        "comment": request.comment,
    }
    try:
        await publish_progress(
            thread_id,
            phase="loading",
            message=f"正在恢复工作流，人工动作：{request.action}",
        )
        async with open_workflow() as workflow:
            result = await workflow.ainvoke(Command(resume=human_input), thread_config)
        _save_match_results(db, result)
        response = _build_workflow_response(
            values=result,
            thread_id=thread_id,
            interrupt_payload=_extract_interrupt_payload(result),
        )
        await finish_progress(thread_id, response)
    except asyncio.CancelledError:
        await fail_progress(thread_id, "工作流恢复因服务关闭而中止，请重新检查 checkpoint")
        raise
    except Exception as exc:
        await fail_progress(thread_id, f"恢复工作流失败: {str(exc)}")
    finally:
        db.close()


@router.get("/{thread_id}/state")
async def get_workflow_state(thread_id: str):
    """读取 PostgreSQL checkpoint，供刷新页面后的前端恢复当前工作流。"""
    from app.graph.workflow import open_workflow

    # 后台任务仍在运行时优先返回进程内真实状态，避免把尚未产生排名的中间
    # checkpoint 误判成 completed。最终响应已经产生时也可以直接复用。
    tracker = get_progress_tracker(thread_id)
    if tracker:
        if tracker.response:
            return tracker.response
        latest = tracker.events[-1] if tracker.events else {}
        return {
            "status": tracker.status,
            "message": latest.get("message", "任务正在后台执行"),
            "thread_id": thread_id,
            "job_id": tracker.job_id,
            "progress": latest,
        }

    thread_config = {"configurable": {"thread_id": thread_id}}
    try:
        async with open_workflow() as workflow:
            snapshot = await workflow.aget_state(thread_config)

        values = dict(snapshot.values or {})
        if not values:
            return {
                "status": "not_found",
                "message": "没有找到该工作流",
                "thread_id": thread_id,
            }

        return _build_workflow_response(
            values=values,
            thread_id=thread_id,
            interrupt_payload=_extract_snapshot_interrupt(snapshot),
            next_steps=list(snapshot.next or ()),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"读取工作流状态失败: {str(exc)}") from exc
