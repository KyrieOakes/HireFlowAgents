"""
app/agents/interview_agent.py
==============================
Interview Agent: 面试问题生成 Agent。

职责: 为进入面试的候选人生成定制化面试问题。
问题是"定制化"的 — 根据候选人简历、匹配结果和风险点来设计。

输入: JD profile + Candidate profile + Match result
输出: 结构化面试问题列表

问题类型:
- technical: 技术能力问题 (基于 JD technical_requirements)
- project_deep_dive: 项目深挖问题 (基于 candidate projects)
- behavioral: 行为/沟通/协作问题 (基于 JD soft_skills)
- risk_verification: 风险验证问题 (基于 match_result risks)
"""

from typing import Dict, Any, List
from app.services.llm_service import call_llm_structured, call_llm
from app.schemas.evaluation_schema import InterviewQuestion
from app.utils.config import settings


async def generate_questions(
    jd_profile: Dict[str, Any],
    candidate_profile: Dict[str, Any],
    match_result: Dict[str, Any],
    llm_service=None,  # 预留参数, 保持接口兼容
) -> List[Dict[str, Any]]:
    """
    为单个候选人生成定制化面试问题 (6-10个)。

    问题来源:
    1. 技术问题: 来自 JD 的 required_skills + technical_requirements
    2. 项目深挖: 来自候选人 projects 中的具体项目
    3. 行为问题: 来自 JD 的 soft_skills
    4. 风险验证: 来自 match_result 的 risks 列表

    参数:
        jd_profile: 结构化岗位信息
        candidate_profile: 候选人结构化画像
        match_result: 匹配评分结果 (含 risk 列表)
        llm_service: 保留参数, 未使用 (内部通过 settings 决定调用链)
    返回:
        List[dict]: 面试问题列表
    """
    # 构造系统提示词
    system_prompt = """你是一位资深技术面试官。输出必须使用中文。

【语言要求 - 最高优先级】
所有输出必须是中文。技术术语保留原文。
question 字段: 完整的面试问题, 中文
purpose 字段: 提问目的, 中文
question_type 字段: 英文枚举值

【问题生成规则】
你需要生成 6-10 个面试问题, 覆盖以下 4 种类型:

1. technical (技术问题, 2-3个):
   基于 JD 的技术要求, 考察候选人的技术能力
   例如: "请解释你在 FastAPI 项目中如何处理异步请求和错误处理?"

2. project_deep_dive (项目深挖, 2-3个):
   基于候选人简历中的具体项目, 深入追问细节
   例如: "你在 RAG 项目中具体是如何做 chunking 和 embedding 的?"

3. behavioral (行为问题, 1-2个):
   考察沟通协作、问题解决等软技能
   例如: "请描述一次你在团队中解决技术分歧的经历"

4. risk_verification (风险验证, 1-2个):
   针对匹配结果中的风险点提问, 判断风险是否真实存在
   例如: "你的简历中没有生产部署经验, 请说明你对容器化和CI/CD的了解程度"

【重要规则】
- 问题要具体, 不要泛泛而谈
- 不要编造候选人没有写过的经历
- 风险验证问题必须来自 match_result 中的 risks 字段
- 技术问题必须来自 jd_profile 中的 required_skills 和 technical_requirements
- 每个问题都要有明确的提问目的"""

    # 构造用户消息
    user_message = _build_question_prompt(
        jd_profile=jd_profile,
        candidate_profile=candidate_profile,
        match_result=match_result,
    )

    # 调用 LLM — 用自由文本 (因为需要灵活的问题格式, 不是单一结构化对象)
    # 让 LLM 返回 JSON 列表
    full_prompt = f"""{system_prompt}

请根据以下信息生成面试问题。返回 JSON 数组, 每个元素包含 question_type, question, purpose。

{user_message}

只返回 JSON 数组, 不要加解释或 markdown。"""

    response = call_llm(
        system_prompt=system_prompt,
        user_message=user_message + "\n\n只返回 JSON 数组, 不要加解释。",
    )

    # 解析 JSON 响应
    import json
    try:
        # 清理可能的 markdown 标记
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        questions = json.loads(text)
        if isinstance(questions, dict):
            questions = [questions]
    except json.JSONDecodeError:
        # 回退: 返回一个简单的问题
        questions = [{
            "question_type": "technical",
            "question": f"请介绍你在 {', '.join(jd_profile.get('required_skills', ['相关技术'])[:3])} 方面的经验",
            "purpose": "评估候选人的技术能力",
        }]

    # 确保每个问题有完整字段
    for q in questions:
        if "question_type" not in q:
            q["question_type"] = "technical"
        if "purpose" not in q:
            q["purpose"] = "评估候选人能力"

    return questions


def _build_question_prompt(
    jd_profile: Dict[str, Any],
    candidate_profile: Dict[str, Any],
    match_result: Dict[str, Any],
) -> str:
    """构造面试问题生成的消息。"""
    lines = []
    lines.append("请为以下候选人定制面试问题:\n")

    # 岗位信息
    lines.append("=" * 40)
    lines.append(f"岗位: {jd_profile.get('job_title', '未知')}")
    lines.append(f"必备技能: {', '.join(jd_profile.get('required_skills', []))}")
    lines.append(f"技术要求: {', '.join(jd_profile.get('technical_requirements', []))}")
    if jd_profile.get('soft_skills'):
        lines.append(f"软技能要求: {', '.join(jd_profile.get('soft_skills', []))}")

    # 候选人信息
    lines.append("")
    lines.append("=" * 40)
    lines.append(f"候选人: {candidate_profile.get('name', '未知')}")
    lines.append(f"技能: {', '.join(candidate_profile.get('skills', []))}")

    if candidate_profile.get('projects'):
        lines.append("项目经历:")
        for proj in candidate_profile['projects']:
            lines.append(f"  - {proj.get('name','')}: {proj.get('description','')}")
            lines.append(f"    技术: {', '.join(proj.get('technologies', []))}")

    if candidate_profile.get('work_experience'):
        lines.append("工作经历:")
        for exp in candidate_profile['work_experience']:
            lines.append(f"  - {exp.get('title','')} @ {exp.get('company','')}")

    # 风险点
    risks = match_result.get("risks", [])
    if risks:
        lines.append("")
        lines.append("=" * 40)
        lines.append("需验证的风险点 (来自匹配结果):")
        for r in risks:
            lines.append(f"  - {r}")

    return "\n".join(lines)


async def batch_generate_questions(
    jd_profile: Dict[str, Any],
    candidate_profiles: List[Dict[str, Any]],
    match_results: List[Dict[str, Any]],
    selected_ids: List[str],
    llm_service=None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    为选中的候选人批量生成面试问题。

    参数:
        jd_profile: 岗位信息
        candidate_profiles: 所有候选人画像
        match_results: 所有匹配结果
        selected_ids: 被选中的候选人 ID 列表
        llm_service: 保留
    返回:
        dict: {candidate_id: [问题列表]}
    """
    # 构建索引
    profile_map = {p.get("candidate_id", ""): p for p in candidate_profiles}
    match_map = {m.get("candidate_id", ""): m for m in match_results}

    result = {}
    for cid in selected_ids:
        profile = profile_map.get(cid)
        match = match_map.get(cid)
        if profile and match:
            result[cid] = await generate_questions(
                jd_profile=jd_profile,
                candidate_profile=profile,
                match_result=match,
            )

    return result
