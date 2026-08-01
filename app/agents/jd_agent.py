"""
app/agents/jd_agent.py
=======================
JD Agent: 岗位描述分析 Agent。

职责: 读取原始岗位描述文本，调用 LLM 提取结构化信息。
这是整个招聘流程的起点，输出作为后续匹配的基准。

输入: 原始岗位描述文本 (字符串)
输出: JobDescription Pydantic 对象 + ScoringRubric 字典
"""

import re
from typing import Dict, Any, List

from app.services.llm_service import call_llm_structured
from app.schemas.jd_schema import JobDescription


# 常见 JD 章节名。解析原文时遇到这些标题就切换内容区域，不能把它们当岗位名称。
JD_SECTION_TITLES = {
    "职位描述", "岗位描述", "工作职责", "岗位职责", "职位职责",
    "职位要求", "岗位要求", "任职要求", "任职资格",
}

# 常见工作地点。JD 头部通常只写“上海”而不写“上海市”，因此需要显式识别。
COMMON_LOCATIONS = {
    "北京", "上海", "广州", "深圳", "杭州", "成都", "南京", "武汉",
    "西安", "苏州", "天津", "重庆", "长沙", "厦门", "海外", "远程",
}

# 用于技术要求回填的常见关键词。只在原文确实出现时加入，不会凭空编造。
TECH_KEYWORDS = [
    "C++", "Python", "Java", "Go", "Agent Skills", "OpenCode", "Moltbot",
    "AI Agent", "Agent", "多Agent协作", "算法", "数据结构", "云原生", "容器",
    "函数", "AI网关", "可观测", "鉴权", "记忆", "知识",
]


async def analyze_jd(jd_text: str) -> Dict[str, Any]:
    """
    分析岗位描述，提取结构化信息 + 生成评分 Rubric。

    分两步:
    第1步: 调用 LLM 提取结构化 JD 信息 (JobDescription)
    第2步: 基于提取结果，生成评分 Rubric (各维度权重)

    参数:
        jd_text: 用户上传的原始岗位描述全文
    返回:
        dict: {
            "job_title": str,
            "required_skills": [str],
            "preferred_skills": [str],
            "responsibilities": [str],
            "education_requirements": [str],
            "experience_requirements": str,
            "technical_requirements": [str],
            "soft_skills": [str],
            "company": str | None,
            "location": str | None,
        }
    """
    # ================================================================
    # 第1步: 提取结构化 JD 信息
    # ================================================================
    # 构造系统提示词: 告诉 LLM 它的角色和任务
    system_prompt = """你是一位资深的招聘专家，输出必须使用中文。

【语言要求 - 最高优先级】
所有文字输出必须是中文。技术术语（Python, Docker等）保留原文。
例如: "Machine Learning" 写成 "机器学习", "Python" 保留 "Python"

【提取规则】
1. 必备技能(required_skills): 岗位明确要求的技能
2. 加分技能(preferred_skills): "优先"、"加分"的技能
3. 岗位职责(responsibilities): 主要工作内容, 用中文描述
4. 学历要求(education_requirements): 学历和专业要求, 用中文
5. 经验要求(experience_requirements): 如"0-2年", 保持原文格式
6. 技术要求(technical_requirements): 具体技术栈, 保留原文
7. 软技能(soft_skills): 用中文描述

【重要】
- 找不到的信息用空列表[], 不要编造
- 不要编造JD中没有的信息"""

    # 调用 LLM 进行结构化提取
    # 传入 JobDescription Pydantic 类，LLM 会按这个格式输出
    jd_profile = call_llm_structured(
        system_prompt=system_prompt,
        user_message=f"请分析以下岗位描述:\n\n{jd_text}",
        output_schema=JobDescription,
    )

    # 将 Pydantic 对象转为字典 (方便后续 JSON 序列化和存储)
    from app.services.llm_service import _fix_unicode_strings
    jd_dict = _fix_unicode_strings(jd_profile.model_dump())

    # Pydantic 只能保证字段类型，不能识别字符串里的韩文、转义碎片或职位 ID。
    # 因此保存前必须结合原始 JD 做第二层清洗和确定性回填。
    jd_dict = _sanitize_jd_profile(jd_dict, jd_text)

    # ================================================================
    # 第2步: 生成评分 Rubric
    # ================================================================
    rubric = _generate_rubric(jd_dict)

    # 将 rubric 附加到 jd_dict 中一起返回
    jd_dict["rubric"] = rubric

    return jd_dict


def _normalize_jd_lines(jd_text: str) -> List[str]:
    """把 Markdown JD 整理为没有空行、粗体符号和多余空格的文本行。"""
    lines: List[str] = []
    for raw_line in (jd_text or "").splitlines():
        # 用户经常直接从网页复制 **职位描述**，这里去掉 Markdown 装饰。
        line = re.sub(r"^[#>*`\-\s]+|[#*`\s]+$", "", raw_line).strip()
        line = re.sub(r"\s{2,}", " ", line)
        if line:
            lines.append(line)
    return lines


def _looks_corrupted(value: Any) -> bool:
    """判断字段是否含有明显乱码、转义碎片或截断 JSON。"""
    if value is None:
        return False
    text = str(value)
    if not text:
        return False

    # 韩文、无效字节转义、代理字符和替换字符都是截图中已经出现的污染特征。
    if re.search(r"[\uac00-\ud7af]|\\x[0-9a-fA-F]{2}|\\u[dD][0-9a-fA-F]{3}|\ufffd", text):
        return True
    if any(0xD800 <= ord(char) <= 0xDFFF for char in text):
        return True

    # 反斜杠与 JSON 标点密集时，内容通常是模型输出的截断片段。
    escape_count = text.count("\\")
    json_punctuation = len(re.findall(r"[{}\[\]\"]", text))
    return escape_count >= 1 or json_punctuation / max(len(text), 1) > 0.2


def _clean_text(value: Any) -> str:
    """清洗普通 JD 字段；明显损坏时直接返回空字符串。"""
    if value is None or _looks_corrupted(value):
        return ""
    text = str(value)
    text = text.replace("\\n", " ").replace("\\r", " ").replace("\\t", " ")
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = text.replace("\ufeff", "").strip(" \"'“”‘’")
    return re.sub(r"\s{2,}", " ", text).strip()


def _clean_list(values: Any) -> List[str]:
    """清洗字符串列表并去重，丢弃每个已经损坏的列表项。"""
    if not isinstance(values, list):
        return []
    result: List[str] = []
    seen = set()
    for value in values:
        clean = _clean_text(value)
        if clean and clean not in seen:
            result.append(clean)
            seen.add(clean)
    return result


def _strip_number_prefix(line: str) -> str:
    """去掉“1、”“2.”等编号，只保留职责或要求正文。"""
    return re.sub(r"^\s*\d+\s*[、.．]\s*", "", line or "").strip()


def _split_jd_sections(lines: List[str]) -> Dict[str, List[str]]:
    """按照职位描述、职位要求等标题切分原始 JD。"""
    sections: Dict[str, List[str]] = {"header": []}
    current = "header"
    for line in lines:
        normalized_title = line.strip("：:")
        if normalized_title in JD_SECTION_TITLES:
            current = "requirements" if "要求" in normalized_title or "资格" in normalized_title else "description"
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _numbered_items(lines: List[str]) -> List[str]:
    """从某个 JD 章节中提取有序编号条目。"""
    items: List[str] = []
    for line in lines:
        if re.match(r"^\s*\d+\s*[、.．]", line):
            clean = _strip_number_prefix(line)
            if clean:
                items.append(clean)
    return items


def _extract_source_title(lines: List[str], model_title: str) -> str:
    """优先保留可信模型标题；标题污染时从 JD 头部提取。"""
    clean_model_title = _clean_text(model_title)
    # 职位 ID 形如 A31360A；它不能进入岗位名称。
    contains_job_id = bool(re.search(r"(?:职位\s*ID|\b[A-Z]\d{4,}[A-Z]?\b)", clean_model_title, flags=re.IGNORECASE))
    if clean_model_title and not contains_job_id:
        return clean_model_title

    # 只有包含章节或职位 ID 的完整 JD，才把第一行视为标题。
    # 单独的“空JD”等测试/占位文本不能被误判为真实岗位名称。
    has_jd_structure = any(
        line.strip("：:") in JD_SECTION_TITLES or re.search(r"职位\s*ID", line, flags=re.IGNORECASE)
        for line in lines
    )
    for line in lines[:10]:
        has_explicit_label = bool(re.match(r"^(?:岗位名称|职位名称|岗位|职位)\s*[:：]", line))
        if not has_jd_structure and not has_explicit_label:
            continue
        candidate = re.sub(r"^(?:岗位名称|职位名称|岗位|职位)\s*[:：]\s*", "", line).strip()
        if not candidate or candidate.strip("：:") in JD_SECTION_TITLES:
            continue
        # 地点、实习类型、部门、项目品牌和职位 ID 都属于头部元数据。
        if (
            candidate in COMMON_LOCATIONS
            or candidate in {"实习", "全职", "兼职", "校招", "社招", "ByteIntern"}
            or re.search(r"职位\s*ID|^研发\s*[-—]", candidate, flags=re.IGNORECASE)
        ):
            continue
        if len(candidate) <= 100:
            return candidate
    return clean_model_title


def _extract_location(lines: List[str], model_location: Any) -> str | None:
    """从可信模型字段或 JD 头部提取工作地点。"""
    clean_model_location = _clean_text(model_location)
    if clean_model_location:
        return clean_model_location
    for line in lines[:10]:
        if line in COMMON_LOCATIONS or re.fullmatch(r"[\u4e00-\u9fff]{2,8}市", line):
            return line
    return None


def _extract_technical_keywords(jd_text: str, current: List[str]) -> List[str]:
    """从原文补回明确出现的技术关键词，并与模型结果去重合并。"""
    result = list(current)
    seen = set(current)
    for keyword in TECH_KEYWORDS:
        # 英文 C 需要单词边界，避免误匹配到其他英文单词内部。
        if keyword == "C++":
            exists = "C++" in jd_text
        else:
            exists = bool(re.search(rf"(?<![A-Za-z]){re.escape(keyword)}(?![A-Za-z])", jd_text, flags=re.IGNORECASE))
        if exists and keyword not in seen:
            result.append(keyword)
            seen.add(keyword)
    return result


def _split_required_skill_item(item: str) -> List[str]:
    """把同一条要求中的多个技术条件拆成便于匹配的独立技能要求。"""
    # 例如“掌握算法...，至少熟练使用一门语言”应拆成两个匹配条件。
    parts = re.split(r"[，,；;](?=至少|并且|同时|熟练|掌握)", item)
    return [part.strip() for part in parts if part.strip()]


def _sanitize_jd_profile(profile: Dict[str, Any], jd_text: str) -> Dict[str, Any]:
    """
    清洗完整 JD 画像，并从原文回填可以确定的信息。

    LLM 负责理解语义；这层负责确保最终保存的每个字段可读、可追溯，
    尤其避免职位名称和匹配标准被乱码污染。
    """
    lines = _normalize_jd_lines(jd_text)
    sections = _split_jd_sections(lines)
    responsibility_items = _numbered_items(sections.get("description", []))
    requirement_items = _numbered_items(sections.get("requirements", []))

    required_skills = _clean_list(profile.get("required_skills"))
    preferred_skills = _clean_list(profile.get("preferred_skills"))
    responsibilities = _clean_list(profile.get("responsibilities"))
    education_requirements = _clean_list(profile.get("education_requirements"))
    technical_requirements = _clean_list(profile.get("technical_requirements"))
    soft_skills = _clean_list(profile.get("soft_skills"))

    # 带编号的职位描述来自用户原文，完整性高于可能截断的模型列表。
    if responsibility_items:
        responsibilities = responsibility_items

    # 如果原文存在编号要求，就按语义重新构造字段，避免保留“202处届”这类
    # 字符合法但并不存在于原文的模型幻觉，也避免把“热爱编程”错放到优先项。
    if requirement_items:
        source_required_skills: List[str] = []
        source_preferred_skills: List[str] = []
        source_education: List[str] = []
        source_soft_skills: List[str] = []

        for item in requirement_items:
            if re.search(r"优先|加分", item):
                source_preferred_skills.append(item)
            if re.search(r"学历|本科|硕士|博士|专业", item):
                source_education.append(item)
            if re.search(r"掌握|熟练|编程语言|算法|数据结构", item):
                source_required_skills.extend(_split_required_skill_item(item))
            if re.search(r"积极乐观|责任心|认真细致|沟通|协作|学习能力|求知欲|好奇心|进取心", item):
                source_soft_skills.append(item)

        if source_required_skills:
            required_skills = source_required_skills
        if source_preferred_skills:
            preferred_skills = source_preferred_skills
        if source_education:
            education_requirements = source_education
        if source_soft_skills:
            soft_skills = source_soft_skills

    technical_requirements = _extract_technical_keywords(jd_text, technical_requirements)

    return {
        "job_title": _extract_source_title(lines, profile.get("job_title", "")),
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "responsibilities": responsibilities,
        "education_requirements": education_requirements,
        "experience_requirements": _clean_text(profile.get("experience_requirements")) or None,
        "company": _clean_text(profile.get("company")) or None,
        "location": _extract_location(lines, profile.get("location")),
        "technical_requirements": technical_requirements,
        "soft_skills": soft_skills,
    }


def _generate_rubric(jd_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    根据岗位需求生成评分 Rubric (各维度权重)。

    默认权重分配:
    - 技术技能匹配: 30 分 (最重要的维度，因为大多数岗位都看重技术)
    - 项目相关性: 20 分
    - 工作经验: 15 分
    - 教育背景: 10 分
    - 领域相关性: 10 分
    - 沟通表达: 5 分
    - 风险扣分: -10 分 (额外扣分项)

    后续可以根据岗位类型动态调整:
    - 技术岗: 技术技能权重更高
    - 管理岗: 经验+沟通权重更高

    参数:
        jd_dict: 结构化 JD 信息
    返回:
        dict: 评分 Rubric
    """
    # 当前使用固定权重 (MVP 阶段)
    # 后续 Phase 会升级为 LLM 动态权重
    rubric = {
        "technical_skills": {"max_score": 30, "weight": 0.30},
        "project_relevance": {"max_score": 20, "weight": 0.20},
        "experience": {"max_score": 15, "weight": 0.15},
        "education": {"max_score": 10, "weight": 0.10},
        "domain_relevance": {"max_score": 10, "weight": 0.10},
        "communication": {"max_score": 5, "weight": 0.05},
        "risk_penalty": {"max_score": -10, "weight": -0.10},
        "total": 100,
    }
    return rubric
