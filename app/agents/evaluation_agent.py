"""
app/agents/evaluation_agent.py
===============================
Evaluation Agent: 面试评价 Agent。

职责: 面试结束后，根据面试官反馈对候选人进行结构化评价。
不自动做录用决定，只生成评价建议供人工审核。

输入: 面试反馈文本 + Candidate profile + Match result + JD profile
输出: 结构化面试评价 (含 recommendation 建议)
"""

from typing import Dict, Any
from app.services.llm_service import call_llm_structured, call_llm
from app.utils.config import settings


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

    # 调用 LLM — 在用户消息末尾再次强调中文
    response = call_llm(
        system_prompt=system_prompt,
        user_message=user_message + "\n\n【重要】用中文输出 JSON。strengths/concerns/summary 必须是中文。不要输出英文。",
    )

    # 解析 JSON (4种策略提取)
    from app.services.llm_service import parse_json_response
    # 用 sentinel 对象检测解析是否成功
    _SENTINEL = object()
    parsed = parse_json_response(response, default=_SENTINEL)
    result = {} if parsed is _SENTINEL else parsed

    # 解析失败: 用正则从原文提取字段值 (比清洗JSON更可读)
    if parsed is _SENTINEL:
        import re
        result["technical_depth_score"] = 5
        result["communication_score"] = 5
        result["problem_solving_score"] = 5
        result["risk_resolution"] = []
        result["recommendation"] = "Hold"
        # 尝试从原文提取字段
        for field, pattern in [
            ("summary", r'"summary"\s*:\s*"([^"]+)"'),
            ("summary2", r'summary\s*:\s*([^\n]+)'),
        ]:
            m = re.search(pattern, response or "")
            if m:
                result["summary"] = m.group(1).strip()
                break
        # 提取 strengths 数组内容
        m = re.search(r'"strengths"\s*:\s*\[(.*?)\]', response or "", re.DOTALL)
        if m:
            items = re.findall(r'"([^"]+)"', m.group(1))
            result["strengths"] = items[:3] if items else []
        else:
            result["strengths"] = []
        # 提取 concerns
        m = re.search(r'"concerns"\s*:\s*\[(.*?)\]', response or "", re.DOTALL)
        if m:
            items = re.findall(r'"([^"]+)"', m.group(1))
            result["concerns"] = items[:3] if items else []
        else:
            result["concerns"] = []
        # summary 兜底
        if not result.get("summary"):
            result["summary"] = (response or "解析失败")[:300]

    # 强制字段 (安全锁)
    result["requires_human_review"] = True
    if "recommendation" not in result:
        result["recommendation"] = "Hold"
    if "risk_resolution" not in result:
        result["risk_resolution"] = []
    if "strengths" not in result:
        result["strengths"] = []
    if "concerns" not in result:
        result["concerns"] = []

    return result


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
