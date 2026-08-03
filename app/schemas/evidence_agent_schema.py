"""
app/schemas/evidence_agent_schema.py
====================================
受控 ReAct 证据 Agent 的结构化数据模型。

这些 Pydantic 模型统一约束 Agent 状态、Tool Calling 轨迹、错误分类和
人工介入信息，避免前后端依赖松散的自由格式字典。
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# Agent 最终状态使用固定枚举，前端可以据此选择颜色和交互。
EvidenceAgentStatus = Literal[
    "completed",
    "insufficient_evidence",
    "needs_human_review",
]

# 错误类别决定系统应该自动重试、让 Agent 改参数，还是立即交给人工。
AgentErrorCategory = Literal[
    "transient",
    "invalid_input",
    "permanent",
    "security",
    "unknown",
]


class ToolCallTrace(BaseModel):
    """
    记录一次工具调用的完整审计信息。

    输入是模型生成的工具名与参数，输出是执行状态、尝试次数和结果摘要；
    该模型不会保存模型隐藏思维链，只保存可验证的行动记录。
    """

    call_id: str
    iteration: int = Field(ge=1)
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    status: Literal["success", "empty", "correctable_error", "failed", "blocked"]
    attempts: int = Field(default=1, ge=1)
    duration_ms: int = Field(default=0, ge=0)
    result_count: int = Field(default=0, ge=0)
    observation_summary: str = ""
    error_category: Optional[AgentErrorCategory] = None
    error_message: Optional[str] = None


class EvidenceAgentError(BaseModel):
    """描述需要记录或交给人工处理的 Agent 错误。"""

    code: str
    category: AgentErrorCategory
    message: str
    retryable: bool
    tool_name: Optional[str] = None
    attempts: int = Field(default=1, ge=1)


class EvidenceAgentRun(BaseModel):
    """
    单个候选人的 ReAct 证据检索结果。

    输出同时包含最终证据和执行轨迹，既能交给 Match Agent，也能在前端
    展示 Agent 如何调用工具、何时重试以及为什么停止。
    """

    candidate_id: str
    status: EvidenceAgentStatus
    iterations: int = Field(default=0, ge=0)
    model_retry_count: int = Field(default=0, ge=0)
    tool_call_count: int = Field(default=0, ge=0)
    tool_calls: List[ToolCallTrace] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    coverage_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    covered_dimensions: List[str] = Field(default_factory=list)
    missing_dimensions: List[str] = Field(default_factory=list)
    reason_summary: str = ""
    stop_reason: str
    requires_human_review: bool = False
    errors: List[EvidenceAgentError] = Field(default_factory=list)


class EvidenceIntervention(BaseModel):
    """前端需要展示的一条人工介入请求。"""

    candidate_id: str
    title: str
    message: str
    error_code: str
    available_actions: List[
        Literal["retry_agent", "continue_with_warning", "skip_failed", "abort"]
    ] = Field(
        default_factory=lambda: [
            "retry_agent",
            "continue_with_warning",
            "skip_failed",
            "abort",
        ]
    )
