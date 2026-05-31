"""
app/graph/workflow.py
======================
LangGraph 工作流定义。

使用 StateGraph 将多个 Agent 节点连接成完整的招聘流程。
工作流是系统的"骨架"，定义了节点之间的执行顺序和条件路由。

核心概念:
- StateGraph: 有向图数据结构，节点是处理函数，边是数据流向
- 条件边 (Conditional Edge): 根据状态决定下一步走哪条路径
- 普通边 (Edge): 固定从 A 节点到 B 节点
"""

from langgraph.graph import StateGraph, END
from app.graph.state import HiringState
from app.graph import nodes


def build_workflow() -> StateGraph:
    """
    构建完整的招聘筛选工作流。

    返回一个编译好的 StateGraph 实例，可以直接运行。

    流程: START -> JD Agent -> Resume Agent -> Resume Validation
           -> Evidence Retrieval -> Match Agent -> Ranking Agent
           -> Human Review -> END

    返回:
        StateGraph: 编译后的 LangGraph 工作流对象
    """
    # 创建 StateGraph，指定使用 HiringState 作为共享状态类型
    # StateGraph 是 LangGraph 的核心类，代表一个有向状态图
    workflow = StateGraph(HiringState)

    # ---- 添加节点 ----
    # add_node(name, function): 向图中注册一个处理节点
    # name 参数是在图中引用该节点的名称
    # function 参数是实现该节点逻辑的异步函数
    workflow.add_node("jd_agent", nodes.jd_agent_node)
    workflow.add_node("resume_agent", nodes.resume_agent_node)
    workflow.add_node("resume_validation", nodes.resume_validation_node)
    workflow.add_node("evidence_retrieval", nodes.evidence_retrieval_node)
    workflow.add_node("match_agent", nodes.match_agent_node)
    workflow.add_node("ranking_agent", nodes.ranking_agent_node)
    workflow.add_node("human_review", nodes.human_review_node)
    workflow.add_node("error_handler", nodes.error_handler_node)

    # ---- 设置入口 ----
    # set_entry_point: 定义工作流从哪个节点开始执行
    workflow.set_entry_point("jd_agent")

    # ---- 添加普通边 (固定路径) ----
    # add_edge(from, to): 定义从 from 节点执行完后无条件进入 to 节点
    # 这些边构成了工作流的主干路径
    workflow.add_edge("jd_agent", "resume_agent")
    workflow.add_edge("resume_agent", "resume_validation")
    workflow.add_edge("evidence_retrieval", "match_agent")
    workflow.add_edge("match_agent", "ranking_agent")
    workflow.add_edge("ranking_agent", "human_review")
    workflow.add_edge("human_review", END)  # END 是 LangGraph 的特殊节点，表示工作流结束

    # ---- 添加条件边 (根据状态决定路径) ----
    # add_conditional_edges(from, condition_function, path_mapping):
    # - from: 源节点名
    # - condition_function: 决定走哪条路径的判断函数
    # - path_mapping: 将判断函数的返回值映射到目标节点名

    # 简历验证后的分支: 成功 -> 进入检索，失败 -> 错误处理
    workflow.add_conditional_edges(
        "resume_validation",
        _check_resume_validation,  # 条件判断函数
        {
            "success": "evidence_retrieval",  # 验证通过 -> 继续检索证据
            "failure": "error_handler",       # 验证失败 -> 错误处理节点
        },
    )

    # 错误处理后的分支: 如果有错误 -> 结束流程并报告
    workflow.add_conditional_edges(
        "error_handler",
        _check_errors,
        {
            "end": END,  # 错误无法恢复 -> 结束工作流
            "retry": "resume_agent",  # 可重试错误 -> 回到简历解析 (未实现)
        },
    )

    # 编译工作流，返回可执行对象
    # compile() 会检查图结构是否有环路、是否所有路径最终都能到达 END
    return workflow.compile()


# ---- 条件判断函数 ----
# 这些函数在运行时被调用，接收当前 state，返回一个字符串决定走哪条路径

def _check_resume_validation(state: HiringState) -> str:
    """
    检查简历验证结果，决定下一步路由。

    参数:
        state: 当前工作流全局状态
    返回:
        str: "success" 或 "failure"
    """
    # 如果 errors 列表不为空，说明有解析失败的简历
    # bool([]) 是 False，bool(["有错误"]) 是 True
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
    # 例如: PDF 格式损坏 -> 不可重试; 网络超时 -> 可重试
    # 当前简化为: 所有错误都直接结束
    return "end"
