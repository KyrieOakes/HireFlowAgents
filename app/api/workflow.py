"""
app/api/workflow.py
====================
LangGraph 工作流 API (含 Human-in-the-loop)。

POST /workflow/run           → 启动完整招聘工作流
POST /workflow/{thread_id}/resume → 人工审核后继续执行
GET  /workflow/{thread_id}/state  → 查看工作流当前状态
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/workflow", tags=["workflow"])


# ---- 请求模型 ----

class WorkflowRunRequest(BaseModel):
    """启动工作流的请求。"""
    jd_text: str
    resume_texts: List[dict]  # [{"candidate_id":"","text":"","filename":""}]


class ResumeRequest(BaseModel):
    """恢复工作流的请求，可用于证据介入或最终排名审核。"""
    # 排名审核: approve_shortlist / reject / modify
    # 证据介入: retry_agent / continue_with_warning / skip_failed / abort
    action: str = "approve_shortlist"
    selected_candidate_ids: List[str] = []
    comment: str = ""


# ---- API ----

@router.post("/run")
async def run_workflow(request: WorkflowRunRequest):
    """
    启动完整招聘筛选工作流。

    流程: JD Agent → Resume Agent → RAG检索 → Match → Ranking → Human Review(暂停)
    工作流会在 Human Review 节点暂停, 等待人工确认。
    """
    from app.graph.workflow import build_workflow
    from app.graph.state import HiringState

    # 构建初始状态
    initial_state: HiringState = {
        "job_id": "",
        "jd_text": request.jd_text,
        "jd_profile": {},
        "resume_texts": request.resume_texts,
        "candidate_profiles": [],
        "resume_chunks": [],
        "retrieved_evidence": {},
        "evidence_agent_runs": [],
        "evidence_interventions": [],
        "evidence_review_status": "",
        "match_results": [],
        "ranking_results": [],
        "selected_candidate_ids": [],
        "interview_questions": {},
        "interview_feedback": {},
        "final_evaluations": {},
        "email_drafts": {},
        "human_review_status": "",
        "errors": [],
    }

    # 构建工作流
    workflow = build_workflow()

    # 使用固定 thread_id 运行
    thread_config = {"configurable": {"thread_id": "hireflow-run-1"}}

    try:
        # 运行工作流直到 interrupt
        result = await workflow.ainvoke(initial_state, thread_config)
        evidence_interventions = result.get("evidence_interventions", [])
        workflow_status = result.get("human_review_status") or (
            "evidence_agent_needs_review" if evidence_interventions else "running"
        )
        return {
            "status": workflow_status,
            "message": "工作流已暂停, 等待人工审核",
            "thread_id": "hireflow-run-1",
            "ranking": result.get("ranking_results", {}),
            "evidence_agent_runs": result.get("evidence_agent_runs", []),
            "evidence_interventions": evidence_interventions,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"工作流执行失败: {str(e)}")


@router.post("/{thread_id}/resume")
async def resume_workflow(
    thread_id: str,
    request: ResumeRequest,
):
    """
    人工审核后恢复工作流。

    传入审核决定 (approve/reject/modify), 工作流从中断点继续。
    """
    from app.graph.workflow import build_workflow

    workflow = build_workflow()
    thread_config = {"configurable": {"thread_id": thread_id}}

    # 构建人工决策
    human_input = {
        "action": request.action,
        "selected_candidate_ids": request.selected_candidate_ids,
        "comment": request.comment,
    }

    try:
        # LangGraph 标准 resume: 用 Command(resume=human_input) 从中断点继续
        from langgraph.types import Command
        result = await workflow.ainvoke(
            Command(resume=human_input),
            thread_config,
        )
        return {
            "status": result.get("human_review_status", "unknown"),
            "selected_candidate_ids": result.get("selected_candidate_ids", []),
            "message": "工作流已继续",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"恢复失败: {str(e)}")


@router.get("/{thread_id}/state")
async def get_workflow_state(thread_id: str):
    """
    查看工作流当前状态 (用于前端轮询/显示进度)。
    """
    from app.graph.workflow import build_workflow

    workflow = build_workflow()
    thread_config = {"configurable": {"thread_id": thread_id}}

    try:
        state = workflow.get_state(thread_config)
        if state is None:
            return {"status": "not_found", "message": "没有找到该工作流"}
        evidence_interventions = state.values.get("evidence_interventions", [])
        workflow_status = state.values.get("human_review_status") or (
            "evidence_agent_needs_review" if evidence_interventions else "running"
        )
        return {
            "status": workflow_status,
            "next_step": str(state.next) if state.next else "interrupted",
            "errors": state.values.get("errors", []),
            "evidence_agent_runs": state.values.get("evidence_agent_runs", []),
            "evidence_interventions": evidence_interventions,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
