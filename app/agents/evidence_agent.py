"""
app/agents/evidence_agent.py
============================
受控 ReAct 证据检索 Agent。

该 Agent 被嵌入确定性的招聘工作流中，只负责从单个候选人的简历中寻找
可引用证据。模型通过原生 Tool Calling 决定查询词，工具返回 Observation，
模型再决定是否继续检索；整个循环由 LangGraph 子图控制轮数和停止条件。

安全边界：
- 只能读取当前候选人的简历证据，禁止跨候选人查询。
- 不允许给候选人打分，也不允许作出录用或淘汰决定。
- 不保存模型隐藏思维链，只记录 Tool Call、Observation 摘要和停止原因。
- 临时基础设施错误自动重试；永久错误和安全错误交给人工处理。
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypedDict

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import Annotated

from app.schemas.evidence_agent_schema import (
    EvidenceAgentError,
    EvidenceAgentRun,
    EvidenceIntervention,
    ToolCallTrace,
)
from app.services.llm_service import _get_llm
from app.services.rag_service import search_evidence
from app.utils.config import settings


# 所有允许检索的评分维度都在白名单中，模型不能自行创造敏感维度。
ALLOWED_DIMENSIONS = {
    "technical_skills",
    "project_relevance",
    "experience",
    "education",
    "domain_relevance",
}

# 本地模型有时会使用更自然的短名称，先映射为系统内部标准维度。
DIMENSION_ALIASES = {
    "technical": "technical_skills",
    "technical_skill": "technical_skills",
    "skills": "technical_skills",
    "skill": "technical_skills",
    "技术": "technical_skills",
    "技术技能": "technical_skills",
    "project": "project_relevance",
    "projects": "project_relevance",
    "project_experience": "project_relevance",
    "项目": "project_relevance",
    "项目经验": "project_relevance",
    "work_experience": "experience",
    "工作经验": "experience",
    "经历": "experience",
    "edu": "education",
    "教育": "education",
    "学历": "education",
    "domain": "domain_relevance",
    "行业": "domain_relevance",
    "领域": "domain_relevance",
}

# 只兼容语义完全相同的工具名，其他未知工具仍会被拒绝并要求模型修正。
TOOL_NAME_ALIASES = {
    "search_evidence": "search_resume_evidence",
    "resume_search": "search_resume_evidence",
    "search_resume": "search_resume_evidence",
    "check_evidence_coverage": "inspect_evidence_coverage",
    "inspect_coverage": "inspect_evidence_coverage",
}

# 受保护属性不会参与证据搜索或候选人评分。
PROTECTED_ATTRIBUTE_TERMS = {
    "年龄",
    "性别",
    "民族",
    "婚姻",
    "生育",
    "宗教",
    "政治面貌",
    "户籍",
    "照片",
}

# 英文单词必须按词边界匹配，否则 "age" 会误伤 "Agent"。
PROTECTED_ATTRIBUTE_ENGLISH_TERMS = {
    "age",
    "gender",
    "race",
    "religion",
    "marital",
}


class EvidenceSecurityError(Exception):
    """模型尝试越权或检索受保护属性时抛出的安全异常。"""


class RetryExhaustedError(Exception):
    """临时错误达到最大尝试次数后抛出的包装异常。"""

    def __init__(self, original: Exception, attempts: int):
        """保存原始异常和总尝试次数，供错误路由生成可解释结果。"""
        super().__init__(str(original))
        self.original = original
        self.attempts = attempts


class EvidenceAgentState(TypedDict, total=False):
    """LangGraph 子图在 ReAct 循环中传递的内部状态。"""

    # add_messages 会把每个节点返回的新消息追加到历史，而不是覆盖旧消息。
    messages: Annotated[List[BaseMessage], add_messages]
    iterations: int
    model_retry_count: int
    tool_call_count: int
    successful_search_count: int
    correctable_error_count: int
    evidence: List[Dict[str, Any]]
    tool_calls: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]
    seen_tool_signatures: List[str]
    fatal_error: Optional[Dict[str, Any]]


# 搜索函数允许在测试中注入假的 Qdrant 实现，生产环境默认调用真实 RAG 服务。
SearchFunction = Callable[..., List[Dict[str, Any]]]
# 睡眠函数也允许注入，单元测试不需要真的等待指数退避时间。
SleepFunction = Callable[[float], Awaitable[None]]


def _required_dimensions(jd_profile: Dict[str, Any]) -> List[str]:
    """
    根据 JD 字段确定需要覆盖的证据维度。

    输入是结构化 JD，输出是固定白名单中的维度列表；没有对应要求的维度
    不会强迫 Agent 搜索，避免为了凑覆盖率生成无意义查询。
    """
    dimensions: List[str] = []

    if jd_profile.get("required_skills") or jd_profile.get("technical_requirements"):
        dimensions.append("technical_skills")
    if jd_profile.get("responsibilities") or jd_profile.get("preferred_skills"):
        dimensions.append("project_relevance")
    if jd_profile.get("experience_requirements"):
        dimensions.append("experience")
    if jd_profile.get("education_requirements"):
        dimensions.append("education")
    if jd_profile.get("industry") or jd_profile.get("domain_requirements"):
        dimensions.append("domain_relevance")

    # 某些历史 JD 字段较少，至少检索技术、项目和经历三个核心维度。
    return dimensions or ["technical_skills", "project_relevance", "experience"]


def _normalize_dimension(
    raw_dimension: Any,
    query: str,
    required_dimensions: List[str],
) -> str:
    """
    把本地模型的维度别名转换成系统标准字段。

    模型省略 dimension 时会根据查询词做轻量判断；仍无法判断时选择当前 JD
    的第一个必需维度，避免仅因非核心展示参数缺失就终止整批匹配。
    """
    normalized = str(raw_dimension or "").strip().lower()
    if normalized in ALLOWED_DIMENSIONS:
        return normalized
    if normalized in DIMENSION_ALIASES:
        return DIMENSION_ALIASES[normalized]

    lowered_query = query.lower()
    if any(term in lowered_query for term in ["项目", "project", "职责", "落地"]):
        return "project_relevance"
    if any(term in lowered_query for term in ["经验", "年限", "experience", "任职"]):
        return "experience"
    if any(term in lowered_query for term in ["教育", "学历", "学校", "education", "degree"]):
        return "education"
    if any(term in lowered_query for term in ["行业", "领域", "domain", "industry"]):
        return "domain_relevance"
    if query:
        return "technical_skills"
    return required_dimensions[0] if required_dimensions else "technical_skills"


def _fallback_query_for_dimension(
    dimension: str,
    jd_profile: Dict[str, Any],
) -> str:
    """模型没有生成 query 时，依据 JD 为当前维度构造安全的确定性查询。"""
    if dimension == "technical_skills":
        parts = (
            jd_profile.get("required_skills", [])[:5]
            + jd_profile.get("technical_requirements", [])[:4]
        )
    elif dimension == "project_relevance":
        parts = (
            jd_profile.get("responsibilities", [])[:3]
            + jd_profile.get("preferred_skills", [])[:3]
        )
    elif dimension == "experience":
        requirement = jd_profile.get("experience_requirements", "")
        parts = [requirement, "项目职责 工作经验 任职时间"]
    elif dimension == "education":
        parts = jd_profile.get("education_requirements", [])[:4]
    else:
        parts = [
            jd_profile.get("industry", ""),
            jd_profile.get("job_title", ""),
            "领域相关经验",
        ]

    query = " ".join(str(part).strip() for part in parts if str(part).strip())
    # 极少数历史 JD 全为空时仍给出可执行的通用查询，不让工具收到空字符串。
    return query[:300] or f"{jd_profile.get('job_title', '岗位')} 相关项目经验"


def _contains_protected_attribute(query: str) -> bool:
    """检查查询词是否包含招聘评分中禁止使用的受保护属性。"""
    normalized = query.lower()
    if any(term in normalized for term in PROTECTED_ATTRIBUTE_TERMS):
        return True
    # \b 只匹配完整英文单词，避免 age/Agent 这种子串假阳性。
    return any(
        re.search(rf"\b{re.escape(term)}\b", normalized)
        for term in PROTECTED_ATTRIBUTE_ENGLISH_TERMS
    )


def _error_category(error: Exception) -> str:
    """
    把底层异常分成重试、修正参数、直接失败和安全阻断四类。

    返回的字符串会写入结构化审计记录，并决定是否执行指数退避。
    """
    if isinstance(error, EvidenceSecurityError):
        return "security"
    if isinstance(error, (ValueError, TypeError)):
        return "invalid_input"
    if isinstance(error, (TimeoutError, ConnectionError, httpx.TimeoutException, httpx.NetworkError)):
        return "transient"

    # OpenAI/Qdrant/HTTP 客户端的异常类型不同，因此兼容读取 status_code。
    status_code = getattr(error, "status_code", None)
    response = getattr(error, "response", None)
    if status_code is None and response is not None:
        status_code = getattr(response, "status_code", None)
    if status_code == 429 or (isinstance(status_code, int) and status_code >= 500):
        return "transient"
    if isinstance(status_code, int) and 400 <= status_code < 500:
        return "permanent"
    return "unknown"


def _is_retryable(error: Exception) -> bool:
    """只有临时基础设施错误才原参数自动重试。"""
    return _error_category(error) == "transient"


async def _invoke_with_retry(
    operation: Callable[[], Awaitable[Any]],
    *,
    max_attempts: int,
    initial_interval: float,
    sleep_fn: SleepFunction,
) -> tuple[Any, int]:
    """
    使用指数退避执行异步操作。

    max_attempts 包含第一次调用。例如值为 3 时，最多执行一次初始调用和
    两次自动重试；非临时错误不会浪费时间重试。
    """
    last_error: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await operation(), attempt
        except Exception as error:
            last_error = error
            if not _is_retryable(error):
                raise RetryExhaustedError(error, attempt) from error
            if attempt < max_attempts:
                # 0.5、1、2 秒这种退避可以缓解限流和短暂网络抖动。
                await sleep_fn(initial_interval * (2 ** (attempt - 1)))

    # 循环结束时 last_error 一定存在；兜底异常只为满足类型检查。
    raise RetryExhaustedError(last_error or RuntimeError("未知调用错误"), max_attempts)


def _build_tool_schemas() -> List[Any]:
    """
    创建暴露给模型的 Tool Calling Schema。

    工具真正的执行由 LangGraph 的受控 tools 节点完成，这样才能统一进行
    候选人隔离、错误分类、重试、审计和人工升级。
    """

    @tool
    def search_resume_evidence(
        dimension: str,
        query: str,
        top_k: int = 3,
        candidate_id: str = "",
    ) -> Dict[str, Any]:
        """
        在当前候选人的简历向量索引中搜索某个评分维度的原文证据。

        candidate_id 由运行时自动注入，模型可以留空；如果主动填写，则只能填写
        当前候选人 ID。
        """
        # 这个函数体不会直接执行，受控 tools 节点会按照同一参数执行真实检索。
        return {
            "candidate_id": candidate_id,
            "dimension": dimension,
            "query": query,
            "top_k": top_k,
        }

    @tool
    def inspect_evidence_coverage() -> Dict[str, Any]:
        """检查目前有哪些评分维度已经找到证据，以及还缺少哪些维度。"""
        # 覆盖率依赖图状态，因此真实计算发生在受控 tools 节点中。
        return {}

    return [search_resume_evidence, inspect_evidence_coverage]


def _coverage(
    evidence: List[Dict[str, Any]],
    required_dimensions: List[str],
) -> tuple[List[str], List[str], float]:
    """根据证据上的 dimension 标签计算覆盖维度、缺失维度和覆盖率。"""
    covered_set = {
        item.get("dimension")
        for item in evidence
        if item.get("dimension") in required_dimensions
    }
    covered = [dimension for dimension in required_dimensions if dimension in covered_set]
    missing = [dimension for dimension in required_dimensions if dimension not in covered_set]
    rate = len(covered) / len(required_dimensions) if required_dimensions else 1.0
    return covered, missing, round(rate, 3)


def _deduplicate_evidence(evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按证据文本去重，同时保留第一次出现时的查询和维度信息。"""
    seen: set[str] = set()
    unique: List[Dict[str, Any]] = []

    for item in evidence:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        key = text[:200]
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    # Match Agent 的 prompt 已有限长保护，这里再限制最多保留 12 条审计证据。
    return unique[:12]


def _build_prompt(
    candidate_id: str,
    candidate_profile: Dict[str, Any],
    jd_profile: Dict[str, Any],
    required_dimensions: List[str],
) -> List[BaseMessage]:
    """构造 ReAct Agent 的系统边界和精简任务上下文。"""
    system_prompt = """你是 HireFlow 的简历证据检索 Agent。

你的任务不是给候选人评分，而是使用工具寻找可引用的简历原文证据。
你必须至少调用一次 search_resume_evidence，再根据 Observation 决定是否换查询词继续搜索。
必要时调用 inspect_evidence_coverage 查看缺失维度。

严格规则：
1. candidate_id 由系统自动注入，调用工具时不要填写 candidate_id。
2. 禁止搜索年龄、性别、民族、婚姻、宗教等受保护属性。
3. 查询词必须短且具体；没有结果时应改写查询，而不是重复完全相同的参数。
4. 不得作出录用、淘汰或最终排名决定。
5. 证据足够或无法继续时，用一句简短中文总结结束；不要输出隐藏思维链。
"""

    # 只传入检索所需的摘要，避免把整份简历重复塞进上下文。
    task_payload = {
        "candidate_id": candidate_id,
        "required_dimensions": required_dimensions,
        "job": {
            "title": jd_profile.get("job_title", ""),
            "required_skills": jd_profile.get("required_skills", [])[:10],
            "technical_requirements": jd_profile.get("technical_requirements", [])[:8],
            "responsibilities": jd_profile.get("responsibilities", [])[:6],
            "experience_requirements": jd_profile.get("experience_requirements", ""),
            "education_requirements": jd_profile.get("education_requirements", [])[:4],
        },
        "candidate_summary": {
            "skills": candidate_profile.get("skills", [])[:15],
            "projects": [
                {
                    "name": project.get("name", ""),
                    "technologies": project.get("technologies", [])[:8],
                }
                for project in candidate_profile.get("projects", [])[:5]
                if isinstance(project, dict)
            ],
            "estimated_years_of_experience": candidate_profile.get(
                "estimated_years_of_experience"
            ),
        },
    }

    return [
        SystemMessage(content=system_prompt),
        HumanMessage(content=json.dumps(task_payload, ensure_ascii=False)),
    ]


async def run_evidence_agent(
    *,
    jd_profile: Dict[str, Any],
    candidate_profile: Dict[str, Any],
    model: Any = None,
    search_fn: SearchFunction = search_evidence,
    sleep_fn: SleepFunction = asyncio.sleep,
    max_iterations: Optional[int] = None,
    max_tool_calls: Optional[int] = None,
    max_attempts: Optional[int] = None,
) -> EvidenceAgentRun:
    """
    为一个候选人运行受控 ReAct 证据子图。

    输入是 JD、候选人画像和可选测试依赖；输出是结构化 EvidenceAgentRun。
    子图包含 reason → tools → reason 循环，并在轮数、工具数、错误或模型
    主动结束时停止。
    """
    candidate_id = str(candidate_profile.get("candidate_id", "")).strip()
    required_dimensions = _required_dimensions(jd_profile)
    agent_config = settings.evidence_agent
    iteration_limit = max_iterations or agent_config.max_iterations
    tool_call_limit = max_tool_calls or agent_config.max_tool_calls
    attempt_limit = max_attempts or agent_config.max_attempts
    llm = model or _get_llm()
    tool_schemas = _build_tool_schemas()

    if not candidate_id:
        error = EvidenceAgentError(
            code="MISSING_CANDIDATE_ID",
            category="permanent",
            message="候选人缺少 candidate_id，无法隔离检索范围",
            retryable=False,
        )
        return EvidenceAgentRun(
            candidate_id="unknown",
            status="needs_human_review",
            stop_reason="permanent_input_error",
            requires_human_review=True,
            missing_dimensions=required_dimensions,
            errors=[error],
        )

    # bind_tools 会把两个 Python 工具的参数 Schema 发送给模型，模型返回原生 tool_calls。
    bound_model = llm.bind_tools(tool_schemas)

    async def reason_node(state: EvidenceAgentState) -> Dict[str, Any]:
        """调用模型决定下一次 Tool Call，临时模型错误按指数退避重试。"""
        iteration = state.get("iterations", 0) + 1

        async def invoke_model() -> AIMessage:
            """执行一次模型调用并确保返回 LangChain AIMessage。"""
            response = await bound_model.ainvoke(state.get("messages", []))
            if not isinstance(response, AIMessage):
                raise TypeError("Agent 模型没有返回 AIMessage")
            return response

        try:
            response, attempts = await _invoke_with_retry(
                invoke_model,
                max_attempts=attempt_limit,
                initial_interval=agent_config.initial_retry_interval,
                sleep_fn=sleep_fn,
            )
            return {
                "messages": [response],
                "iterations": iteration,
                "model_retry_count": state.get("model_retry_count", 0) + attempts - 1,
            }
        except RetryExhaustedError as wrapped:
            original = wrapped.original
            category = _error_category(original)
            error = EvidenceAgentError(
                code="MODEL_CALL_FAILED",
                category=category if category != "invalid_input" else "permanent",
                message=f"Agent 模型调用失败: {original}",
                retryable=_is_retryable(original),
                attempts=wrapped.attempts,
            )
            return {
                "iterations": iteration,
                "model_retry_count": state.get("model_retry_count", 0)
                + max(0, wrapped.attempts - 1),
                "fatal_error": error.model_dump(),
                "errors": state.get("errors", []) + [error.model_dump()],
            }

    async def tools_node(state: EvidenceAgentState) -> Dict[str, Any]:
        """
        执行模型生成的 Tool Calls，并统一处理隔离、重试、Observation 和审计。
        """
        messages = state.get("messages", [])
        last_message = messages[-1] if messages else None
        if not isinstance(last_message, AIMessage):
            return state

        evidence = list(state.get("evidence", []))
        traces = list(state.get("tool_calls", []))
        errors = list(state.get("errors", []))
        seen_signatures = list(state.get("seen_tool_signatures", []))
        tool_messages: List[ToolMessage] = []
        tool_call_count = state.get("tool_call_count", 0)
        successful_search_count = state.get("successful_search_count", 0)
        correctable_error_count = state.get("correctable_error_count", 0)
        fatal_error: Optional[Dict[str, Any]] = None

        for raw_call in last_message.tool_calls:
            # 达到工具预算后不再执行新的外部调用，避免模型无限循环。
            if tool_call_count >= tool_call_limit:
                break

            tool_call_count += 1
            call_id = str(raw_call.get("id") or f"tool-{tool_call_count}")
            raw_tool_name = str(raw_call.get("name", ""))
            tool_name = TOOL_NAME_ALIASES.get(raw_tool_name, raw_tool_name)
            raw_arguments = raw_call.get("args", {}) or {}
            # 某些 OpenAI 兼容本地模型会把 args 返回成 JSON 字符串，这里先做兼容解析。
            if isinstance(raw_arguments, str):
                try:
                    raw_arguments = json.loads(raw_arguments)
                except json.JSONDecodeError:
                    raw_arguments = {}
            arguments = dict(raw_arguments) if isinstance(raw_arguments, dict) else {}
            started_at = time.perf_counter()
            attempts = 1
            result_count = 0
            status = "success"
            observation: Dict[str, Any]
            error_category: Optional[str] = None
            error_message: Optional[str] = None

            try:
                if tool_name == "search_resume_evidence":
                    supplied_candidate = str(arguments.get("candidate_id", "")).strip()
                    # query_text/search_query 是本地模型常见的同义参数名。
                    query = str(
                        arguments.get("query")
                        or arguments.get("query_text")
                        or arguments.get("search_query")
                        or ""
                    ).strip()
                    dimension = _normalize_dimension(
                        arguments.get("dimension")
                        or arguments.get("category")
                        or arguments.get("evidence_type"),
                        query,
                        required_dimensions,
                    )
                    if not query:
                        query = _fallback_query_for_dimension(dimension, jd_profile)
                    top_k = arguments.get("top_k", 3)

                    # 数字字符串是本地模型常见输出，可以无损转换为整数。
                    if isinstance(top_k, str) and top_k.isdigit():
                        top_k = int(top_k)

                    # 空 ID 代表让运行时注入当前候选人；只有主动填写其他非空 ID
                    # 才属于真正的跨候选人访问并触发安全阻断。
                    if supplied_candidate and supplied_candidate != candidate_id:
                        raise EvidenceSecurityError(
                            f"禁止跨候选人检索: 当前 {candidate_id}, 请求 {supplied_candidate}"
                        )
                    if dimension not in ALLOWED_DIMENSIONS:
                        raise ValueError(f"不支持的证据维度: {dimension}")
                    if len(query) > 300:
                        raise ValueError("query 必须是 1-300 字符的具体检索词")
                    if _contains_protected_attribute(query):
                        raise EvidenceSecurityError("查询包含招聘中禁止使用的受保护属性")
                    if not isinstance(top_k, int) or not 1 <= top_k <= 5:
                        raise ValueError("top_k 必须是 1-5 之间的整数")

                    signature = json.dumps(
                        {
                            "tool": tool_name,
                            "candidate_id": candidate_id,
                            "dimension": dimension,
                            "query": query,
                            "top_k": top_k,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    if signature in seen_signatures:
                        raise ValueError("完全相同的 Tool Call 已经执行过，请改写查询")
                    seen_signatures.append(signature)

                    # 审计轨迹记录系统实际执行的规范参数，而不是模型的残缺原始参数。
                    arguments = {
                        "candidate_id": candidate_id,
                        "dimension": dimension,
                        "query": query,
                        "top_k": top_k,
                    }

                    async def execute_search() -> List[Dict[str, Any]]:
                        """在线程中执行同步 Qdrant 检索，避免阻塞 FastAPI 事件循环。"""
                        return await asyncio.to_thread(
                            search_fn,
                            query_text=query,
                            candidate_id=candidate_id,
                            top_k=top_k,
                        )

                    results, attempts = await _invoke_with_retry(
                        execute_search,
                        max_attempts=attempt_limit,
                        initial_interval=agent_config.initial_retry_interval,
                        sleep_fn=sleep_fn,
                    )
                    successful_search_count += 1

                    enriched_results: List[Dict[str, Any]] = []
                    for item in results or []:
                        enriched = dict(item)
                        enriched["dimension"] = dimension
                        enriched["query"] = query
                        enriched_results.append(enriched)
                    evidence = _deduplicate_evidence(evidence + enriched_results)
                    result_count = len(enriched_results)
                    status = "success" if result_count else "empty"
                    observation = {
                        "status": status,
                        "dimension": dimension,
                        "query": query,
                        "result_count": result_count,
                        "results": enriched_results[:5],
                    }

                elif tool_name == "inspect_evidence_coverage":
                    covered, missing, rate = _coverage(evidence, required_dimensions)
                    observation = {
                        "status": "success",
                        "covered_dimensions": covered,
                        "missing_dimensions": missing,
                        "coverage_rate": rate,
                    }

                else:
                    raise ValueError(f"未授权或不存在的工具: {tool_name}")

            except Exception as caught:
                # 参数校验错误在调用外部工具前发生，不会经过重试包装；这里把
                # 两种异常统一分类，确保非法 Tool Call 也能作为 Observation 返回。
                if isinstance(caught, RetryExhaustedError):
                    original = caught.original
                    attempts = caught.attempts
                else:
                    original = caught
                    attempts = 1
                error_category = _error_category(original)
                error_message = str(original)

                if error_category == "invalid_input":
                    # 参数错误作为 Observation 返回，让模型有机会修改参数重新规划。
                    correctable_error_count += 1
                    status = "correctable_error"
                    observation = {
                        "status": status,
                        "error": error_message,
                        "instruction": "请修改工具参数后再试，不要重复相同调用。",
                        "valid_example": {
                            "name": "search_resume_evidence",
                            "args": {
                                "dimension": required_dimensions[0],
                                "query": _fallback_query_for_dimension(
                                    required_dimensions[0], jd_profile
                                ),
                                "top_k": 3,
                            },
                        },
                    }
                    if correctable_error_count >= agent_config.max_correctable_errors:
                        error = EvidenceAgentError(
                            code="TOOL_ARGUMENT_REPAIR_EXHAUSTED",
                            category="invalid_input",
                            message="模型连续产生非法 Tool Call，已停止自动修正",
                            retryable=False,
                            tool_name=tool_name,
                            attempts=correctable_error_count,
                        )
                        fatal_error = error.model_dump()
                        errors.append(error.model_dump())
                else:
                    # 临时错误重试耗尽、永久错误、安全错误和未知错误都交给人工。
                    status = "blocked" if error_category == "security" else "failed"
                    code = {
                        "transient": "TOOL_RETRY_EXHAUSTED",
                        "permanent": "TOOL_PERMANENT_ERROR",
                        "security": "TOOL_SECURITY_BLOCKED",
                        "unknown": "TOOL_UNKNOWN_ERROR",
                    }.get(error_category, "TOOL_EXECUTION_ERROR")
                    error = EvidenceAgentError(
                        code=code,
                        category=error_category,
                        message=f"工具 {tool_name} 执行失败: {error_message}",
                        retryable=error_category == "transient",
                        tool_name=tool_name,
                        attempts=attempts,
                    )
                    fatal_error = error.model_dump()
                    errors.append(error.model_dump())
                    observation = {
                        "status": status,
                        "error": error_message,
                        "requires_human_review": True,
                    }

            duration_ms = max(0, int((time.perf_counter() - started_at) * 1000))
            summary = (
                f"找到 {result_count} 条证据"
                if status == "success" and tool_name == "search_resume_evidence"
                else "工具执行成功"
                if status == "success"
                else "未找到证据"
                if status == "empty"
                else error_message or str(observation.get("error", "工具执行失败"))
            )
            trace = ToolCallTrace(
                call_id=call_id,
                iteration=state.get("iterations", 1),
                tool_name=tool_name,
                arguments=arguments,
                status=status,
                attempts=attempts,
                duration_ms=duration_ms,
                result_count=result_count,
                observation_summary=summary,
                error_category=error_category,
                error_message=error_message,
            )
            traces.append(trace.model_dump())
            tool_messages.append(
                ToolMessage(
                    content=json.dumps(observation, ensure_ascii=False, default=str),
                    tool_call_id=call_id,
                    name=tool_name or "unknown_tool",
                )
            )

            # 安全或不可恢复错误发生后立即停止，不继续执行同一批的剩余工具。
            if fatal_error:
                break

        return {
            "messages": tool_messages,
            "evidence": evidence,
            "tool_calls": traces,
            "errors": errors,
            "seen_tool_signatures": seen_signatures,
            "tool_call_count": tool_call_count,
            "successful_search_count": successful_search_count,
            "correctable_error_count": correctable_error_count,
            "fatal_error": fatal_error,
        }

    def force_tool_node(state: EvidenceAgentState) -> Dict[str, Any]:
        """模型未调用工具时提醒一次，确保该节点真正体现 Tool Calling。"""
        return {
            "messages": [
                HumanMessage(
                    content=(
                        "你还没有调用检索工具。请先调用 search_resume_evidence，"
                        "不要直接根据候选人画像给结论。"
                    )
                )
            ]
        }

    def route_after_reason(state: EvidenceAgentState) -> str:
        """根据最新模型消息决定执行工具、强制工具调用或结束。"""
        if state.get("fatal_error"):
            return "end"
        messages = state.get("messages", [])
        last_message = messages[-1] if messages else None
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
        if (
            state.get("successful_search_count", 0) == 0
            and state.get("iterations", 0) < iteration_limit
        ):
            return "force_tool"
        return "end"

    def route_after_tools(state: EvidenceAgentState) -> str:
        """工具执行后检查安全错误、轮数预算和工具预算。"""
        if state.get("fatal_error"):
            return "end"
        if state.get("tool_call_count", 0) >= tool_call_limit:
            return "end"
        if state.get("iterations", 0) >= iteration_limit:
            return "end"
        return "reason"

    # 这个小图就是项目中的受控 ReAct 子图：reason 与 tools 形成反馈循环。
    builder = StateGraph(EvidenceAgentState)
    builder.add_node("reason", reason_node)
    builder.add_node("tools", tools_node)
    builder.add_node("force_tool", force_tool_node)
    builder.add_edge(START, "reason")
    builder.add_conditional_edges(
        "reason",
        route_after_reason,
        {"tools": "tools", "force_tool": "force_tool", "end": END},
    )
    builder.add_edge("force_tool", "reason")
    builder.add_conditional_edges(
        "tools",
        route_after_tools,
        {"reason": "reason", "end": END},
    )
    graph = builder.compile()

    initial_state: EvidenceAgentState = {
        "messages": _build_prompt(
            candidate_id,
            candidate_profile,
            jd_profile,
            required_dimensions,
        ),
        "iterations": 0,
        "model_retry_count": 0,
        "tool_call_count": 0,
        "successful_search_count": 0,
        "correctable_error_count": 0,
        "evidence": [],
        "tool_calls": [],
        "errors": [],
        "seen_tool_signatures": [],
        "fatal_error": None,
    }
    final_state = await graph.ainvoke(
        initial_state,
        # 给图本身再加一道递归上限，防止未来修改路由时意外形成无限循环。
        {"recursion_limit": iteration_limit * 3 + 4},
    )

    evidence = _deduplicate_evidence(final_state.get("evidence", []))
    covered, missing, coverage_rate = _coverage(evidence, required_dimensions)
    fatal_error = final_state.get("fatal_error")
    successful_search_count = final_state.get("successful_search_count", 0)

    if fatal_error:
        status = "needs_human_review"
        stop_reason = str(fatal_error.get("code", "agent_error")).lower()
        requires_human_review = True
    elif evidence:
        status = "completed"
        stop_reason = "evidence_collected"
        requires_human_review = False
    elif successful_search_count > 0:
        # 工具正常但搜不到证据是业务结果，不应伪装成基础设施错误。
        status = "insufficient_evidence"
        stop_reason = "search_completed_without_evidence"
        requires_human_review = True
    else:
        error = EvidenceAgentError(
            code="AGENT_BUDGET_EXHAUSTED",
            category="unknown",
            message="Agent 达到轮数或工具预算，但没有完成有效检索",
            retryable=True,
        )
        final_state["errors"] = final_state.get("errors", []) + [error.model_dump()]
        status = "needs_human_review"
        stop_reason = "agent_budget_exhausted"
        requires_human_review = True

    # 最后一条非 Tool 的模型文本作为可展示摘要；不保存隐藏推理过程。
    reason_summary = ""
    for message in reversed(final_state.get("messages", [])):
        if isinstance(message, AIMessage) and message.content and not message.tool_calls:
            reason_summary = str(message.content).strip()[:500]
            break
    if not reason_summary:
        reason_summary = (
            f"已覆盖 {len(covered)}/{len(required_dimensions)} 个证据维度"
        )

    return EvidenceAgentRun(
        candidate_id=candidate_id,
        status=status,
        iterations=final_state.get("iterations", 0),
        model_retry_count=final_state.get("model_retry_count", 0),
        tool_call_count=final_state.get("tool_call_count", 0),
        tool_calls=[ToolCallTrace.model_validate(item) for item in final_state.get("tool_calls", [])],
        evidence=evidence,
        coverage_rate=coverage_rate,
        covered_dimensions=covered,
        missing_dimensions=missing,
        reason_summary=reason_summary,
        stop_reason=stop_reason,
        requires_human_review=requires_human_review,
        errors=[
            EvidenceAgentError.model_validate(item)
            for item in final_state.get("errors", [])
        ],
    )


async def batch_collect_evidence(
    *,
    jd_profile: Dict[str, Any],
    candidate_profiles: List[Dict[str, Any]],
) -> tuple[Dict[str, List[Dict[str, Any]]], List[EvidenceAgentRun]]:
    """
    依次运行候选人的证据 Agent。

    本地 LM Studio 通常一次只能稳定处理少量请求，因此这里先使用顺序执行；
    Match Agent 后续仍保留线程池并行评分。
    """
    evidence_by_candidate: Dict[str, List[Dict[str, Any]]] = {}
    runs: List[EvidenceAgentRun] = []

    for profile in candidate_profiles:
        run = await run_evidence_agent(
            jd_profile=jd_profile,
            candidate_profile=profile,
        )
        runs.append(run)
        evidence_by_candidate[run.candidate_id] = run.evidence

    return evidence_by_candidate, runs


def build_interventions(runs: List[EvidenceAgentRun]) -> List[EvidenceIntervention]:
    """把不可自动恢复的 Agent 结果转换成前端可操作的人工介入项。"""
    interventions: List[EvidenceIntervention] = []

    for run in runs:
        if run.status != "needs_human_review":
            continue
        first_error = run.errors[0] if run.errors else None
        interventions.append(
            EvidenceIntervention(
                candidate_id=run.candidate_id,
                title="证据 Agent 需要人工选择",
                message=(
                    first_error.message
                    if first_error
                    else "Agent 未在预算内完成证据检索"
                ),
                error_code=first_error.code if first_error else "AGENT_UNKNOWN_ERROR",
            )
        )

    return interventions
