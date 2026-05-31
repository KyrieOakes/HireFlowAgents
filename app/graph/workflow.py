"""
app/graph/workflow.py
======================
LangGraph 工作流定义 (PostgresSaver 持久化)。

使用 StateGraph 将多个 Agent 节点连接成完整的招聘流程。
PostgresSaver 是 LangGraph 官方推荐的生产级 Checkpointer:
- 工作流状态持久化到 PostgreSQL
- 支持 Human-in-the-loop 中断恢复
- 支持跨天执行 (面试流程可能跨多天)

核心概念:
- StateGraph: 有向图，节点是处理函数，边是数据流向
- PostgresSaver: 将状态图执行进度保存到 PostgreSQL
- 条件边 (Conditional Edge): 根据状态决定下一步走哪条路径
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from app.graph.state import HiringState
from app.graph import nodes
from app.utils.config import settings


def build_checkpointer() -> PostgresSaver:
    """
    创建 PostgresSaver 实例。

    PostgresSaver 使用 PostgreSQL 存储工作流的 checkpoint。
    每次节点执行后，状态自动保存到数据库。
    如果流程被中断 (如 Human Review 节点)，下次可以从中断点恢复。

    返回:
        PostgresSaver: 配置好的 checkpointer 实例
    """
    # 从配置中读取数据库连接 URL
    # PostgresSaver 需要自己的数据库连接来管理 checkpoint 表
    checkpointer = PostgresSaver.from_conn_string(settings.database.url)

    # 首次使用时自动创建 checkpoint 相关表
    # setup() 会建两张表: checkpoints 和 checkpoint_writes
    checkpointer.setup()

    return checkpointer


def build_workflow() -> StateGraph:
    """
    构建完整的招聘筛选工作流。

    流程: START -> JD Agent -> Resume Agent -> Resume Validation
           -> Evidence Retrieval -> Match Agent -> Ranking Agent
           -> Human Review -> END

    返回:
        StateGraph: 编译后的 LangGraph 工作流对象
    """
    # 创建 StateGraph，指定 HiringState 作为共享状态类型
    workflow = StateGraph(HiringState)

    # ---- 添加节点 ----
    # add_node(name, function): 向图中注册一个处理节点
    workflow.add_node("jd_agent", nodes.jd_agent_node)
    workflow.add_node("resume_agent", nodes.resume_agent_node)
    workflow.add_node("resume_validation", nodes.resume_validation_node)
    workflow.add_node("evidence_retrieval", nodes.evidence_retrieval_node)
    workflow.add_node("match_agent", nodes.match_agent_node)
    workflow.add_node("ranking_agent", nodes.ranking_agent_node)
    workflow.add_node("human_review", nodes.human_review_node)
    workflow.add_node("error_handler", nodes.error_handler_node)

    # ---- 设置入口 ----
    workflow.set_entry_point("jd_agent")

    # ---- 添加普通边 (固定路径) ----
    workflow.add_edge("jd_agent", "resume_agent")
    workflow.add_edge("resume_agent", "resume_validation")
    workflow.add_edge("evidence_retrieval", "match_agent")
    workflow.add_edge("match_agent", "ranking_agent")
    workflow.add_edge("ranking_agent", "human_review")
    workflow.add_edge("human_review", END)

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
    # 注入 PostgresSaver 作为 checkpointer
    # 这样工作流的每个步骤都会自动保存到 PostgreSQL
    checkpointer = build_checkpointer()
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

    参数:
        state: 当前工作流全局状态
    返回:
        str: "end" 结束流程 或 "retry" 重试
    """
    # TODO: 根据错误类型判断是否可重试
    # 例如: PDF 损坏 -> 不可重试; 网络超时 -> 可重试
    return "end"
