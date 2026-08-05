"""
app/graph/workflow.py
======================
LangGraph 工作流定义 (PostgresSaver 持久化)。

使用 StateGraph 将多个 Agent 节点连接成完整的招聘流程。

架构说明:
  - 前端主匹配流程通过 workflow API 进入本状态图
  - 已经解析并保存到数据库的 JD/简历画像会直接复用，避免重复调用 LLM
  - Human-in-the-loop 中断点由 PostgreSQL checkpoint 持久化

PostgresSaver 是 LangGraph 官方推荐的生产级 Checkpointer:
- 工作流状态持久化到 PostgreSQL
- 支持 Human-in-the-loop 中断恢复
- 支持跨天执行 (面试流程可能跨多天)

核心概念:
- StateGraph: 有向图，节点是处理函数，边是数据流向
- PostgresSaver: 将状态图执行进度保存到 PostgreSQL
- 条件边 (Conditional Edge): 根据状态决定下一步走哪条路径
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from langgraph.graph import StateGraph, END
from app.graph.state import HiringState
from app.graph import nodes
from app.utils.config import settings


@asynccontextmanager
async def open_workflow() -> AsyncIterator[Any]:
    """
    打开一个带 PostgreSQL 持久化能力的已编译工作流。

    为什么使用异步上下文管理器:
    - API 使用 ``workflow.ainvoke()``，因此 checkpointer 也必须是异步版本。
    - ``from_conn_string()`` 返回上下文管理器，必须在 ``async with`` 内使用。
    - 请求结束时自动关闭数据库连接，但 checkpoint 数据仍永久保存在 PostgreSQL。

    输出:
        AsyncIterator[Any]: 在上下文中可安全调用的 LangGraph 编译结果。
    """
    # 延迟导入可以让普通 CRUD API 在 checkpoint 驱动尚未安装时仍能启动，
    # 真正调用工作流时则会给出明确的依赖错误。
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    # AsyncPostgresSaver 会为本次 API 调用打开一条异步 PostgreSQL 连接。
    async with AsyncPostgresSaver.from_conn_string(settings.database.url) as checkpointer:
        # setup() 是幂等操作：首次创建表，后续调用只检查迁移版本。
        await checkpointer.setup()

        # 连接保持打开期间编译并交出工作流，保证 ainvoke/aget_state 可正常读写。
        yield build_workflow(checkpointer)


def build_workflow(checkpointer: Any) -> Any:
    """
    构建完整的招聘筛选工作流。

    流程: START -> JD Agent -> Resume Agent -> Resume Validation
           -> Evidence ReAct Agent -> Match Agent -> Ranking Agent
           -> Human Review -> END

    返回:
        checkpointer: LangGraph checkpoint 保存器；生产环境传入 AsyncPostgresSaver，
            测试环境可以传入 InMemorySaver。

    返回:
        Any: 编译后的 LangGraph 工作流对象。
    """
    # 创建 StateGraph，指定 HiringState 作为共享状态类型
    workflow = StateGraph(HiringState)

    # ---- 添加节点 ----
    # add_node(name, function): 向图中注册一个处理节点
    workflow.add_node("jd_agent", nodes.jd_agent_node)
    workflow.add_node("resume_agent", nodes.resume_agent_node)
    workflow.add_node("resume_validation", nodes.resume_validation_node)
    workflow.add_node("evidence_retrieval", nodes.evidence_retrieval_node)
    workflow.add_node("evidence_intervention", nodes.evidence_intervention_node)
    workflow.add_node("match_agent", nodes.match_agent_node)
    workflow.add_node("ranking_agent", nodes.ranking_agent_node)
    workflow.add_node("human_review", nodes.human_review_node)
    workflow.add_node("error_handler", nodes.error_handler_node)

    # ---- 设置入口 ----
    workflow.set_entry_point("jd_agent")

    # ---- 添加普通边 (固定路径) ----
    workflow.add_edge("jd_agent", "resume_agent")
    workflow.add_edge("resume_agent", "resume_validation")
    workflow.add_edge("match_agent", "ranking_agent")
    workflow.add_edge("ranking_agent", "human_review")

    # human_review 后的条件路由: 批准→结束, 驳回→重新匹配
    workflow.add_conditional_edges(
        "human_review",
        _check_review_result,
        {
            "approved": END,           # 批准 → 进入面试流程(后续Phase)
            "modified": END,           # 修改后通过 → 同上
            "rejected": "match_agent", # 驳回 → 重新匹配
            "error": "error_handler",  # 错误 → 错误处理
        },
    )

    # ---- 添加条件边 (根据状态决定路径) ----

    # 简历验证后的分支: 成功 -> 检索，失败 -> 错误处理
    workflow.add_conditional_edges(
        "resume_validation",
        _check_resume_validation,
        {
            "success": "evidence_retrieval",
            "failure": "error_handler",
        },
    )

    # 证据 Agent 成功时进入评分；工具重试耗尽时先暂停并等待人工选择。
    workflow.add_conditional_edges(
        "evidence_retrieval",
        _check_evidence_agent,
        {
            "success": "match_agent",
            "needs_review": "evidence_intervention",
        },
    )

    # 人工可以重跑 Agent、带警告继续、跳过失败候选人或终止流程。
    workflow.add_conditional_edges(
        "evidence_intervention",
        _check_evidence_review,
        {
            "retry": "evidence_retrieval",
            "continue": "match_agent",
            "abort": "error_handler",
        },
    )

    # 错误处理后的分支
    workflow.add_conditional_edges(
        "error_handler",
        _check_errors,
        {
            "end": END,
            "retry": "resume_agent",
        },
    )

    # ---- 编译工作流 ----
    # 注入调用方提供的 checkpointer，使生产环境和测试环境可以使用不同持久化实现。
    return workflow.compile(checkpointer=checkpointer)


# ---- 条件判断函数 ----

def _check_resume_validation(state: HiringState) -> str:
    """
    检查简历验证结果，决定下一步路由。

    参数:
        state: 当前工作流全局状态
    返回:
        str: "success" 或 "failure"
    """
    # 如果 errors 列表不为空，说明有解析失败的简历
    if state.get("errors"):
        return "failure"
    return "success"


def _check_errors(state: HiringState) -> str:
    """
    检查错误是否可以重试。
    """
    return "end"


def _check_evidence_agent(state: HiringState) -> str:
    """检查是否存在必须由人工处理的 Tool Calling 技术错误。"""
    if state.get("evidence_interventions"):
        return "needs_review"
    return "success"


def _check_evidence_review(state: HiringState) -> str:
    """把证据人工节点的选择映射到 LangGraph 下一条边。"""
    status = state.get("evidence_review_status", "abort")
    if status == "retry":
        return "retry"
    if status == "continue":
        return "continue"
    return "abort"


def _check_review_result(state: HiringState) -> str:
    """
    检查人工审核结果, 决定下一步。

    返回:
        "approved": 审核通过 → 进入面试
        "modified": 修改后通过
        "rejected": 驳回 → 回到匹配
        "error": 出错
    """
    status = state.get("human_review_status", "")
    if status == "approved":
        return "approved"
    elif status == "modified":
        return "modified"
    elif status == "rejected":
        return "rejected"
    else:
        return "error"
