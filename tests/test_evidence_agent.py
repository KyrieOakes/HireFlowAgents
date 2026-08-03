"""
tests/test_evidence_agent.py
============================
受控 ReAct 证据 Agent 的单元测试。

测试使用假的 Tool Calling 模型和假的 Qdrant 搜索函数，重点验证反馈循环、
基础设施重试、参数自我修正、安全阻断和证据不足等工程边界。
"""

import asyncio
import os
import sys
from typing import Any, List

from langchain_core.messages import AIMessage

# 测试可以从仓库根目录直接导入 app 包，与现有测试文件保持一致。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.evidence_agent import build_interventions, run_evidence_agent


class FakeToolCallingModel:
    """按顺序返回预设 AIMessage 的最小 Tool Calling 模型。"""

    def __init__(self, responses: List[AIMessage]):
        """保存每轮模型响应，并记录 bind_tools 收到的工具定义。"""
        self.responses = list(responses)
        self.bound_tools: List[Any] = []

    def bind_tools(self, tools: List[Any]):
        """模拟 ChatOpenAI.bind_tools，并返回可异步调用的模型自身。"""
        self.bound_tools = tools
        return self

    async def ainvoke(self, messages: List[Any]) -> AIMessage:
        """返回下一条响应；没有响应时主动结束，避免测试无限循环。"""
        if self.responses:
            return self.responses.pop(0)
        return AIMessage(content="证据检索结束")


def _tool_call(call_id: str, **arguments: Any) -> AIMessage:
    """构造一次 search_resume_evidence 原生 Tool Call。"""
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "search_resume_evidence",
                "args": arguments,
                "id": call_id,
                "type": "tool_call",
            }
        ],
    )


def _jd_profile() -> dict:
    """返回测试使用的最小结构化 JD。"""
    return {
        "job_title": "Agent 开发工程师",
        "required_skills": ["Python", "LangGraph", "RAG"],
        "responsibilities": ["开发 Agent 工作流"],
        "experience_requirements": "有项目实践经验",
    }


def _candidate_profile() -> dict:
    """返回测试使用的最小候选人画像。"""
    return {
        "candidate_id": "C001",
        "skills": ["Python", "LangGraph"],
        "projects": [{"name": "HireFlow", "technologies": ["LangGraph", "Qdrant"]}],
    }


async def _no_sleep(seconds: float) -> None:
    """替代真实指数退避等待，让测试立即完成。"""
    return None


def test_react_agent_calls_tools_and_uses_observations():
    """验证模型可以根据第一次 Observation 改写查询并再次调用工具。"""
    model = FakeToolCallingModel(
        [
            _tool_call(
                "call-1",
                candidate_id="C001",
                dimension="technical_skills",
                query="Python LangGraph Agent 开发",
                top_k=3,
            ),
            _tool_call(
                "call-2",
                candidate_id="C001",
                dimension="experience",
                query="项目职责 实践经验 系统落地",
                top_k=3,
            ),
            AIMessage(content="已找到技术和项目实践证据，可以交给 Match Agent。"),
        ]
    )

    def fake_search(**kwargs: Any) -> list[dict]:
        """按查询词返回不同简历片段，模拟 Agent 动态搜索。"""
        return [
            {
                "text": f"简历证据：{kwargs['query_text']}",
                "score": 0.91,
                "metadata": {"source": "resume.pdf"},
            }
        ]

    result = asyncio.run(
        run_evidence_agent(
            jd_profile=_jd_profile(),
            candidate_profile=_candidate_profile(),
            model=model,
            search_fn=fake_search,
            sleep_fn=_no_sleep,
        )
    )

    assert result.status == "completed", result.model_dump()
    assert result.iterations == 3
    assert result.tool_call_count == 2
    assert len(result.evidence) == 2
    assert result.covered_dimensions == ["technical_skills", "experience"]
    assert {item.name for item in model.bound_tools} == {
        "search_resume_evidence",
        "inspect_evidence_coverage",
    }


def test_transient_tool_error_retries_then_succeeds():
    """验证 TimeoutError 使用相同参数总尝试三次，第三次成功。"""
    model = FakeToolCallingModel(
        [
            _tool_call(
                "retry-call",
                candidate_id="C001",
                dimension="technical_skills",
                query="LangGraph Tool Calling",
                top_k=2,
            ),
            AIMessage(content="重试后已取得证据。"),
        ]
    )
    call_count = 0
    sleep_intervals: list[float] = []

    def flaky_search(**kwargs: Any) -> list[dict]:
        """前两次模拟网络超时，第三次返回正常证据。"""
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise TimeoutError("Qdrant timeout")
        return [{"text": "实现了 LangGraph Tool Calling", "score": 0.9, "metadata": {}}]

    async def record_sleep(seconds: float) -> None:
        """记录指数退避时间但不真正等待。"""
        sleep_intervals.append(seconds)

    result = asyncio.run(
        run_evidence_agent(
            jd_profile=_jd_profile(),
            candidate_profile=_candidate_profile(),
            model=model,
            search_fn=flaky_search,
            sleep_fn=record_sleep,
            max_attempts=3,
        )
    )

    assert result.status == "completed", result.model_dump()
    assert call_count == 3
    assert sleep_intervals == [0.5, 1.0]
    assert result.tool_calls[0].attempts == 3


def test_invalid_tool_arguments_are_returned_for_agent_repair():
    """验证查询参数错误不会原样重试，而是交给模型修改后重新调用。"""
    model = FakeToolCallingModel(
        [
            _tool_call(
                "invalid-call",
                candidate_id="C001",
                dimension="technical_skills",
                query="",
                top_k=3,
            ),
            _tool_call(
                "fixed-call",
                candidate_id="C001",
                dimension="technical_skills",
                query="Python Agent 项目",
                top_k=3,
            ),
            AIMessage(content="参数修正后已找到证据。"),
        ]
    )
    search_count = 0

    def fake_search(**kwargs: Any) -> list[dict]:
        """只有修正后的合法调用才会进入真实搜索函数。"""
        nonlocal search_count
        search_count += 1
        return [{"text": "Python Agent 项目经验", "score": 0.88, "metadata": {}}]

    result = asyncio.run(
        run_evidence_agent(
            jd_profile=_jd_profile(),
            candidate_profile=_candidate_profile(),
            model=model,
            search_fn=fake_search,
            sleep_fn=_no_sleep,
        )
    )

    assert result.status == "completed"
    assert search_count == 1
    assert result.tool_calls[0].status == "correctable_error"
    assert result.tool_calls[1].status == "success"


def test_cross_candidate_tool_call_is_blocked_immediately():
    """验证模型尝试读取其他候选人时不重试并立即要求人工复核。"""
    model = FakeToolCallingModel(
        [
            _tool_call(
                "security-call",
                candidate_id="C999",
                dimension="technical_skills",
                query="Python",
                top_k=3,
            )
        ]
    )
    search_count = 0

    def should_not_run(**kwargs: Any) -> list[dict]:
        """安全校验应在访问向量数据库之前拦截调用。"""
        nonlocal search_count
        search_count += 1
        return []

    result = asyncio.run(
        run_evidence_agent(
            jd_profile=_jd_profile(),
            candidate_profile=_candidate_profile(),
            model=model,
            search_fn=should_not_run,
            sleep_fn=_no_sleep,
        )
    )

    assert result.status == "needs_human_review"
    assert result.requires_human_review is True
    assert search_count == 0
    assert result.tool_calls[0].status == "blocked"
    assert result.errors[0].code == "TOOL_SECURITY_BLOCKED"


def test_empty_search_result_is_business_gap_not_system_error():
    """验证工具正常返回空结果时标记证据不足，而不是误报基础设施错误。"""
    model = FakeToolCallingModel(
        [
            _tool_call(
                "empty-call",
                candidate_id="C001",
                dimension="experience",
                query="工作年限 任职时间",
                top_k=3,
            ),
            AIMessage(content="简历没有明确工作年限，需要人工确认。"),
        ]
    )

    result = asyncio.run(
        run_evidence_agent(
            jd_profile=_jd_profile(),
            candidate_profile=_candidate_profile(),
            model=model,
            search_fn=lambda **kwargs: [],
            sleep_fn=_no_sleep,
        )
    )

    assert result.status == "insufficient_evidence"
    assert result.stop_reason == "search_completed_without_evidence"
    assert result.errors == []
    assert result.tool_calls[0].status == "empty"


def test_retry_exhaustion_creates_human_intervention():
    """验证临时错误总尝试三次仍失败时生成四种人工处理选项。"""
    model = FakeToolCallingModel(
        [
            _tool_call(
                "failed-call",
                candidate_id="C001",
                dimension="technical_skills",
                query="LangGraph Tool Calling",
                top_k=3,
            )
        ]
    )
    call_count = 0

    def unavailable_search(**kwargs: Any) -> list[dict]:
        """模拟 Qdrant 在全部尝试中持续超时。"""
        nonlocal call_count
        call_count += 1
        raise TimeoutError("Qdrant unavailable")

    result = asyncio.run(
        run_evidence_agent(
            jd_profile=_jd_profile(),
            candidate_profile=_candidate_profile(),
            model=model,
            search_fn=unavailable_search,
            sleep_fn=_no_sleep,
            max_attempts=3,
        )
    )
    interventions = build_interventions([result])

    assert call_count == 3
    assert result.status == "needs_human_review"
    assert result.tool_calls[0].attempts == 3
    assert result.errors[0].code == "TOOL_RETRY_EXHAUSTED"
    assert len(interventions) == 1
    assert interventions[0].available_actions == [
        "retry_agent",
        "continue_with_warning",
        "skip_failed",
        "abort",
    ]
