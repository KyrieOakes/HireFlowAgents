"""
app/agents/match_agent.py
==========================
Match Agent: 候选人匹配评分 Agent。

职责: 将每个候选人与岗位描述进行对比，给出基于证据的评分。
这是系统的核心 Agent，决定候选人的排名。

输入: JD profile + Candidate profile + RAG 证据 + Rubric
输出: MatchResult (含各维度分数、证据、风险、推荐等级)

评分维度 (总分 100):
- 技术技能: 30 分
- 项目相关性: 20 分
- 工作经验: 15 分
- 教育背景: 10 分
- 领域相关性: 10 分
- 沟通表达: 5 分
- 风险扣分: -10 分
"""

from typing import Dict, Any, List, Optional
from app.services.llm_service import call_llm_structured
from app.schemas.match_schema import MatchResult, DimensionScores
from app.utils.config import settings


async def match_candidate(
    jd_profile: Dict[str, Any],
    candidate_profile: Dict[str, Any],
    evidence_list: Optional[List[Dict[str, Any]]] = None,
    rubric: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    对单个候选人进行匹配评分。

    这个方法做的事:
    1. 将 JD 要求与候选人画像并排比较
    2. LLM 在 7 个维度上分别打分
    3. 每个得分点都要求有简历证据支撑
    4. 综合分数给出推荐等级

    参数:
        jd_profile: 结构化岗位信息 (来自 JD Agent)
        candidate_profile: 结构化候选人画像 (来自 Resume Agent)
        evidence_list: RAG 检索到的简历证据 (可选, Phase 1.3 使用)
        rubric: 评分标准和各维度权重 (来自 JD Agent)
    返回:
        dict: 匹配评分结果
    """
    # 构造系统提示词
    # 这是整个系统中最关键的 prompt: 它定义了评分的标准和规则
    system_prompt = """你是一位资深的技术面试官和招聘专家。
你的任务是对候选人进行多维度匹配评分。

评分规则:
1. 技术技能匹配 (满分30分):
   - 比较候选人的技能列表和JD的required_skills
   - 完全匹配: 25-30分
   - 大部分匹配: 18-24分
   - 部分匹配: 10-17分
   - 很少匹配: 0-9分

2. 项目相关性 (满分20分):
   - 候选人的项目经历与JD职责的相关程度
   - 技术栈相似、业务领域相同: 16-20分
   - 有一定关联但不完全匹配: 10-15分
   - 基本不相关: 0-9分

3. 工作经验 (满分15分):
   - 工作/实习经历与岗位要求的匹配程度
   - 年限匹配且内容相关: 12-15分
   - 年限不足但内容相关: 7-11分
   - 不相关或无经验: 0-6分

4. 教育背景 (满分10分):
   - 学历和专业是否满足JD要求
   - 完全满足: 8-10分
   - 部分满足: 5-7分
   - 不满足: 0-4分

5. 领域相关性 (满分10分):
   - 候选人是否在相关行业或业务领域有经验
   - 高度相关: 8-10分
   - 有一定相关性: 5-7分
   - 不相关: 0-4分

6. 沟通表达 (满分5分):
   - 从简历文字质量、项目描述清晰度、结构完整性推断
   - 表达清晰结构好: 4-5分
   - 一般: 2-3分
   - 混乱: 0-1分

7. 风险扣分 (0到-10分):
   - 识别潜在风险并扣分，如:
     * 技能明显不足: -3到-5分
     * 频繁跳槽: -2到-4分
     * 经历断层: -2到-3分
     * 学历不达标: -3到-5分

重要规则:
- 每个分数都要给出理由(在strengths或risks字段中说明)
- 如果提供了evidence，必须引用到具体的证据
- 不要编造候选人没有的技能或经验
- 推荐等级: total_score>=80→"Strong Match", 65-79→"Medium Match", 50-64→"Weak Match", <50→"Not Recommended"
- **中文输出**: strengths、risks、summary 必须用中文撰写，技能名和技术术语保留原文
- recommendation 用英文: "Strong Match" / "Medium Match" / "Weak Match" / "Not Recommended"
"""

    # 构造用户消息: 把 JD 和候选人信息组织在一起
    user_message = _build_match_prompt(
        jd_profile=jd_profile,
        candidate_profile=candidate_profile,
        evidence_list=evidence_list,
        rubric=rubric,
    )

    # 调用 LLM 进行结构化评分
    match_result = call_llm_structured(
        system_prompt=system_prompt,
        user_message=user_message,
        output_schema=MatchResult,
    )

    # 转为字典，并确保使用传入的 candidate_id
    result_dict = match_result.model_dump()
    result_dict["candidate_id"] = candidate_profile.get("candidate_id", "unknown")
    return result_dict


def _build_match_prompt(
    jd_profile: Dict[str, Any],
    candidate_profile: Dict[str, Any],
    evidence_list: Optional[List[Dict[str, Any]]] = None,
    rubric: Optional[Dict[str, Any]] = None,
) -> str:
    """
    构造匹配评分的用户消息。

    把 JD 要求、候选人信息和证据组织成清晰的结构，
    方便 LLM 逐项比较评分。

    参数:
        jd_profile: 岗位信息
        candidate_profile: 候选人信息
        evidence_list: RAG 证据
        rubric: 评分标准
    返回:
        str: 格式化的用户消息
    """
    import json

    # 用分隔线让信息块更清晰
    lines = []

    lines.append("请对以下候选人进行匹配评分:\n")

    # 评分标准 (如果有)
    if rubric:
        lines.append("=" * 50)
        lines.append("评分标准 (Rubric):")
        lines.append(json.dumps(rubric, ensure_ascii=False, indent=2))
        lines.append("")

    # 岗位要求
    lines.append("=" * 50)
    lines.append("岗位要求 (JD):")
    lines.append(f"  岗位名称: {jd_profile.get('job_title', '未指定')}")
    lines.append(f"  必备技能: {', '.join(jd_profile.get('required_skills', []))}")
    lines.append(f"  加分技能: {', '.join(jd_profile.get('preferred_skills', []))}")
    lines.append(f"  岗位职责: {', '.join(jd_profile.get('responsibilities', []))}")
    lines.append(f"  学历要求: {', '.join(jd_profile.get('education_requirements', []))}")
    lines.append(f"  经验要求: {jd_profile.get('experience_requirements', '未指定')}")
    lines.append(f"  技术要求: {', '.join(jd_profile.get('technical_requirements', []))}")
    lines.append(f"  软技能: {', '.join(jd_profile.get('soft_skills', []))}")

    # 候选人信息
    lines.append("")
    lines.append("=" * 50)
    lines.append("候选人信息:")
    lines.append(f"  姓名: {candidate_profile.get('name', '未知')}")
    lines.append(f"  技能: {', '.join(candidate_profile.get('skills', []))}")

    if candidate_profile.get('education'):
        lines.append("  教育:")
        for edu in candidate_profile['education']:
            lines.append(f"    - {edu.get('degree', '')} {edu.get('major', '')} @ {edu.get('school', '')}")

    if candidate_profile.get('projects'):
        lines.append("  项目:")
        for proj in candidate_profile['projects']:
            lines.append(f"    - {proj.get('name', '')}: {proj.get('description', '')}")

    if candidate_profile.get('work_experience'):
        lines.append("  工作经历:")
        for exp in candidate_profile['work_experience']:
            lines.append(f"    - {exp.get('title', '')} @ {exp.get('company', '')} ({exp.get('duration', '')})")

    lines.append(f"  估计经验年限: {candidate_profile.get('estimated_years_of_experience', '未知')}")

    # RAG 证据 (如果有)
    if evidence_list:
        lines.append("")
        lines.append("=" * 50)
        lines.append("来自简历的RAG证据 (请引用这些证据支撑你的评分):")
        for i, ev in enumerate(evidence_list):
            lines.append(f"  证据{i+1}: {ev.get('text', '')}")
            lines.append(f"    来源: {ev.get('source', '未知')}")

    lines.append("")
    lines.append("请根据以上信息，对候选人在每个维度上打分。")

    return "\n".join(lines)


async def batch_match_candidates(
    jd_profile: Dict[str, Any],
    candidate_profiles: List[Dict[str, Any]],
    evidence_by_candidate: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    rubric: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    批量对多个候选人进行匹配评分。

    参数:
        jd_profile: 岗位信息 (同一个JD用于所有候选人)
        candidate_profiles: 所有候选人的画像列表
        evidence_by_candidate: {candidate_id: [证据列表]}
        rubric: 评分标准
    返回:
        List[dict]: 所有候选人的匹配评分结果
    """
    results = []

    for profile in candidate_profiles:
        candidate_id = profile.get("candidate_id", "unknown")

        # 获取该候选人的 RAG 证据
        evidence = None
        if evidence_by_candidate:
            evidence = evidence_by_candidate.get(candidate_id)

        # 调用单候选人匹配
        result = await match_candidate(
            jd_profile=jd_profile,
            candidate_profile=profile,
            evidence_list=evidence,
            rubric=rubric,
        )
        results.append(result)

    return results
