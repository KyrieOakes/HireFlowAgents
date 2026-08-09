"""
app/agents/evaluation_agent.py
===============================
Evaluation Agent: 面试评价 Agent。

职责: 面试结束后，根据面试官反馈对候选人进行结构化评价。
不自动做录用决定，只生成评价建议供人工审核。

输入: 面试反馈文本 + Candidate profile + Match result + JD profile
输出: 结构化面试评价 (含 recommendation 建议)
"""

import re
from typing import Dict, Any

from app.schemas.evaluation_schema import InterviewEvaluationOutput
from app.services.llm_service import call_llm_structured


async def evaluate_candidate(
    interview_feedback: str,
    candidate_profile: Dict[str, Any],
    match_result: Dict[str, Any],
    jd_profile: Dict[str, Any],
    llm_service=None,
) -> Dict[str, Any]:
    """
    根据面试反馈生成结构化面试评价。

    评价维度:
    1. 技术深度 (1-10): 候选人对技术的理解和应用能力
    2. 沟通表达 (1-10): 表达清晰度、逻辑性
    3. 问题解决 (1-10): 应对问题的思维方式
    4. 风险解决: 面试前识别的风险点是否被解决

    参数:
        interview_feedback: 面试官填写的面试记录/反馈文本
        candidate_profile: 候选人画像
        match_result: 匹配评分结果 (含风险点)
        jd_profile: 岗位信息
        llm_service: 保留
    返回:
        dict: 结构化评价
    """
    # 构造系统提示词
    system_prompt = """你是一位资深技术面试官。你必须用中文输出。

═══════════════════════════════════
【语言强制要求 — 违反此规则的结果将被丢弃】
═══════════════════════════════════
strengths 必须写中文。例如: "技术基础扎实" ✅   "Strong technical skills" ❌
concerns 必须写中文。例如: "项目经验不足" ✅   "Lack of experience" ❌
summary 必须写中文。例如: "整体表现良好" ✅   "Good performance" ❌
risk_resolution 中的 reason 必须写中文。
技术术语保留原文 (Python, FastAPI, RAG 等)。
═══════════════════════════════════

【评价规则】
1. technical_depth_score (1-10): 技术问答质量
2. communication_score (1-10): 表达清晰度、逻辑性
3. problem_solving_score (1-10): 分析和解决问题能力
4. risk_resolution: 风险点逐一评估
   - resolved: 已解释清楚
   - partially_resolved: 部分解释
   - unresolved: 未涉及
5. strengths: 面试亮点 (中文, 基于实际回答)
6. concerns: 暴露的问题 (中文)
7. summary: 面试总结 (中文, 1-2句)
8. recommendation: 只用英文枚举值
9. requires_human_review: 固定为 true

【JSON 格式示例 — 必须遵守, risk_resolution 是数组不是对象】
{"technical_depth_score":8,"communication_score":7,"problem_solving_score":6,"risk_resolution":[{"risk":"项目经验不足","status":"resolved","reason":"展示了细节"}],"strengths":["技术扎实"],"concerns":["经验偏少"],"summary":"表现良好","recommendation":"Recommend","requires_human_review":true}

【重要规则】
- 必须基于 interview_feedback, 不能只根据简历下结论
- 如果反馈信息不足以判断某个维度, 在 concerns 中说明
- recommendation 只是建议, 不是最终决定
- 不能输出"录用"/"不录用"等最终决策
- 不要编造候选人没有说过的话"""

    # 构造用户消息
    user_message = _build_eval_prompt(
        interview_feedback=interview_feedback,
        candidate_profile=candidate_profile,
        match_result=match_result,
        jd_profile=jd_profile,
    )

    try:
        # 直接让 LangChain + Pydantic约束模型输出，不再手工猜测和修复 JSON。
        structured = await call_llm_structured(
            system_prompt=system_prompt,
            user_message=(
                user_message
                + "\n\n【重要】所有说明字段使用中文，并严格按结构化字段返回。"
            ),
            output_schema=InterviewEvaluationOutput,
        )
        result = structured.model_dump()

        # 即使模型错误地把 JSON 片段放进 summary，也不能把它直接展示到页面。
        summary = str(result.get("summary", "")).strip()
        if _looks_like_serialized_data(summary):
            result["summary"] = _build_safe_summary(interview_feedback)
            result["concerns"] = list(result.get("concerns") or []) + [
                "模型总结格式异常，已使用安全摘要，请人工核对详细评价。"
            ]
    except Exception as exc:
        # 结构化调用失败时返回可读的保守评价，绝不能把模型原始 JSON 塞入 summary。
        print(f"\n[EVAL STRUCTURED FAIL] {type(exc).__name__}: {str(exc)[:300]}\n")
        result = _build_fallback_evaluation(interview_feedback, match_result)

    # 招聘建议必须经过人工审核；这里覆盖模型值形成最后一道安全锁。
    result["requires_human_review"] = True
    return result


def _looks_like_serialized_data(text: str) -> bool:
    """判断 summary 是否误装入了 JSON、Python 字典或字段清单。"""
    if not text:
        return True
    # 截图中的问题文本包含字段名和大量括号，这种内容不能作为自然语言总结展示。
    field_hits = len(
        re.findall(
            r"technical_depth_score|communication_score|risk_resolution|recommendation",
            text,
        )
    )
    bracket_count = sum(text.count(char) for char in "{}[]")
    return field_hits >= 1 or bracket_count >= 4


def _build_safe_summary(interview_feedback: str) -> str:
    """根据人工输入生成短而可读的兜底总结，不引用模型的损坏原文。"""
    # 合并换行和重复空格，避免用户输入撑坏卡片布局。
    clean_feedback = re.sub(r"\s+", " ", interview_feedback or "").strip()
    if not clean_feedback:
        return "面试反馈信息不足，当前评价暂设为待定，请人工补充并审核。"
    preview = clean_feedback[:120]
    return f"已记录面试官反馈：{preview}。当前评价暂设为待定，请人工审核。"


def _build_fallback_evaluation(
    interview_feedback: str,
    match_result: Dict[str, Any],
) -> Dict[str, Any]:
    """在结构化输出失败时构造字段完整、内容可读的保守评价。"""
    # 对每个历史风险标记“尚未确认”，避免失败时错误宣称风险已解决。
    risk_resolution = [
        {
            "risk": str(risk),
            "status": "unresolved",
            "reason": "当前面试反馈不足以确认该风险是否已经解决。",
        }
        for risk in (match_result.get("risks") or [])
    ]
    return {
        "technical_depth_score": 5,
        "communication_score": 5,
        "problem_solving_score": 5,
        "risk_resolution": risk_resolution,
        "strengths": [],
        "concerns": ["结构化评价生成失败，当前结果仅作占位，请人工重新审核。"],
        "summary": _build_safe_summary(interview_feedback),
        "recommendation": "Hold",
        "requires_human_review": True,
    }


def _build_eval_prompt(
    interview_feedback: str,
    candidate_profile: Dict[str, Any],
    match_result: Dict[str, Any],
    jd_profile: Dict[str, Any],
) -> str:
    """构造面试评价的消息。"""
    lines = []
    lines.append("请根据以下信息生成面试评价:\n")

    lines.append("=" * 40)
    lines.append(f"岗位: {jd_profile.get('job_title', '未知')}")

    lines.append("")
    lines.append("=" * 40)
    lines.append(f"候选人: {candidate_profile.get('name', '未知')}")
    lines.append(f"技能: {', '.join(candidate_profile.get('skills', []))}")

    # 匹配阶段的风险点
    risks = match_result.get("risks", [])
    if risks:
        lines.append("")
        lines.append("匹配阶段识别的风险点 (需在面试中验证):")
        for r in risks:
            lines.append(f"  - {r}")

    # 匹配分数
    lines.append("")
    lines.append(f"匹配总分: {match_result.get('total_score', 0)}")
    lines.append(f"推荐等级: {match_result.get('recommendation', '')}")

    # 面试反馈
    lines.append("")
    lines.append("=" * 40)
    lines.append("面试官反馈 (面试记录):")
    lines.append(interview_feedback)

    lines.append("")
    lines.append("请基于以上面试反馈生成结构化评价 (JSON格式)。")

    return "\n".join(lines)
