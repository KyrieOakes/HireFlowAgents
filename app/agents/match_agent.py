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
    system_prompt = """你是一位资深技术面试官，输出必须使用中文。

【语言要求 - 最高优先级】
- strengths(优势): 用中文写
- risks(风险): 用中文写
- summary(总结): 用中文写
- recommendation: 用英文 ("Strong Match"/"Medium Match"/"Weak Match"/"Not Recommended")
- 技术术语保留原文

【评分规则】
1. 技术技能匹配(30分): 比较候选人技能 vs JD required_skills
2. 项目相关性(20分): 候选人项目经验与JD职责匹配度
3. 工作经验(15分): 年限+内容匹配度
4. 教育背景(10分): 学历+专业匹配度
5. 领域相关性(10分): 相关行业经验
6. 沟通表达(5分): 从简历质量推断
7. 风险扣分(0~-10分): 技能不足/跳槽频繁/经历断层/学历不达标

【评分档位】
- 完全匹配: 80-100%
- 大部分匹配: 60-79%
- 部分匹配: 40-59%
- 很少匹配: 0-39%

【重要规则】
- 每个分数给出理由(strengths/risks中)
- 有evidence必须引用
- 不编造信息
- 推荐等级: >=80→"Strong Match", 65-79→"Medium Match", 50-64→"Weak Match", <50→"Not Recommended"
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

    # ---- 后处理: 强制翻译为中文 ----
    # 本地模型 (hermes-3) 可能仍输出英文, 这里做一次批量翻译
    results = await _ensure_chinese_results(results)

    return results


async def _ensure_chinese_results(
    results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    确保 match agent 的输出是中文。

    检测每个结果中的 strengths, risks, summary 是否以英文为主,
    如果是, 用一次批量 LLM 调用翻译为中文。
    """
    # 收集所有需要翻译的文本
    texts_to_translate: List[Tuple[int, str, str]] = []  # (result_index, field_name, text)

    for i, r in enumerate(results):
        for field in ["strengths", "risks", "summary"]:
            value = r.get(field, "")
            if isinstance(value, str) and value.strip():
                if _is_mostly_ascii(value):
                    texts_to_translate.append((i, field, value))
            elif isinstance(value, list):
                for j, item in enumerate(value):
                    if isinstance(item, str) and _is_mostly_ascii(item):
                        texts_to_translate.append((i, f"{field}[{j}]", item))

    if not texts_to_translate:
        return results

    # 构建批量翻译请求
    from app.services.llm_service import call_llm
    items_text = "\n---\n".join(
        f"[{idx}:{field}] {text}"
        for idx, field, text in texts_to_translate
    )

    translation_prompt = f"""将以下英文招聘评价翻译为中文。
保持技术术语原文, 只翻译描述性内容。
输出格式: 每行 [索引:字段] 中文翻译

{items_text}"""

    try:
        translated = call_llm(
            system_prompt="你是专业翻译。只输出翻译结果, 不要解释。",
            user_message=translation_prompt,
        )

        # 解析翻译结果 (格式: [0:strengths] 翻译文字)
        translation_map: Dict[str, str] = {}
        for line in translated.strip().split("\n"):
            line = line.strip()
            if line.startswith("[") and "] " in line:
                key, _, text = line.partition("] ")
                translation_map[key.lstrip("[")] = text

        # 替换回原结果
        for idx, field, _ in texts_to_translate:
            map_key = f"{idx}:{field}"
            if map_key in translation_map:
                translated_text = translation_map[map_key]
                result = results[idx]
                if "[" in field and field.endswith("]"):
                    # 列表元素: "strengths[0]" → result["strengths"][0]
                    field_name, _, idx_str = field.partition("[")
                    idx_int = int(idx_str.rstrip("]"))
                    if isinstance(result.get(field_name), list):
                        result[field_name][idx_int] = translated_text
                else:
                    result[field] = translated_text

    except Exception:
        # 翻译失败不阻塞流程
        pass

    return results


def _is_mostly_ascii(text: str) -> bool:
    """检查文本是否以英文为主 (ASCII字符占比 > 50%)。"""
    if not text:
        return False
    ascii_count = sum(1 for c in text if ord(c) < 128)
    return ascii_count / len(text) > 0.5
