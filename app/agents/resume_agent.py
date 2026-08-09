"""
app/agents/resume_agent.py
===========================
Resume Agent: 简历解析 Agent。

职责: 从原始简历文本中提取候选人结构化画像。
对每份简历调用 LLM，提取教育、技能、项目、工作经历等信息，
并分析候选人的优势和风险点。

输入: 简历纯文本 + 候选人ID
输出: CandidateProfile Pydantic 对象
"""

import re
from typing import Dict, Any, List
from app.services.llm_service import call_llm_structured
from app.schemas.resume_schema import CandidateProfile
from app.utils.config import settings


SECTION_TITLES = {
    "个人信息",
    "基本信息",
    "联系方式",
    "个人概述",
    "个人简介",
    "个人总结",
    "自我评价",
    "求职方向",
    "求职意向",
    "教育经历",
    "项目经历",
    "实习经历",
    "工作经历",
    "技能",
    "专业技能",
    "证书",
    "证书认证",
}


TECH_KEYWORDS = [
    "Python", "RAG", "AI Agent", "LangGraph", "FastAPI", "Pydantic",
    "SQL", "RESTful API", "Pandas", "NumPy", "Matplotlib",
    "Scikit-learn", "BERT", "XGBoost", "Random Forest", "SVM",
    "Logistic Regression", "Git", "GitHub", "pytest", "Docker",
    "Scrum", "Jupyter Notebook", "LLM", "Workflow Design",
    "Human-in-the-Loop",
]


def _has_surrogate_char(text: str) -> bool:
    """
    判断字符串里是否含有无效代理字符。

    Unicode 代理区通常只应该出现在编码内部流程中，
    如果它直接出现在业务字段里，基本可以判断是 LLM 输出污染。
    """
    return any(0xD800 <= ord(char) <= 0xDFFF for char in text)


def _looks_corrupted(text: str) -> bool:
    """
    判断文本是否像乱码。

    这里不是判断内容好不好，而是专门识别这类机器生成污染:
    - \\uD83C 这类残缺代理对
    - \\xC9 这类字节碎片
    - %E7%A6 这类残缺 URL 编码
    - 不应混入中文简历字段的大量韩文字符
    - 大量反斜杠转义碎片
    """
    if not text:
        return False

    escape_count = len(re.findall(r"\\u[dD][0-9a-fA-F]{3}|\\x[0-9a-fA-F]{2}|%[0-9a-fA-F]{2}", text))
    hangul_count = len(re.findall(r"[\uac00-\ud7af]", text))
    slash_count = text.count("\\")
    punctuation_count = len(re.findall(r"[{}\[\]\",]", text))
    surrogate_count = 1 if _has_surrogate_char(text) else 0

    # 短字段里只要出现一次明显乱码标记，就应该丢弃，避免姓名/学校被污染。
    if len(text) < 80 and (escape_count or surrogate_count or slash_count >= 2):
        return True

    # 只有 JSON 残片、括号和逗号的内容不是有效简历字段。
    if punctuation_count / max(len(text), 1) > 0.35:
        return True

    # 技能/经历里混进联系方式时，通常是模型把原文结构打散了。
    if _extract_email(text) or _extract_phone(text):
        return True

    bad_score = escape_count * 3 + hangul_count + slash_count + surrogate_count * 5
    return bad_score / max(len(text), 1) > 0.08


def _is_section_title(text: str) -> bool:
    """
    判断一行文本是否是简历章节标题。

    章节标题不能被当成候选人姓名、学校或公司名。
    """
    return _clean_text(text).strip() in SECTION_TITLES


def _clean_text(value: Any, *, drop_if_corrupted: bool = False) -> str:
    """
    清洗 LLM 输出的普通文本字段。

    参数:
        value: 可能来自 LLM 的任意值
        drop_if_corrupted: 如果字段明显乱码，是否直接返回空字符串
    返回:
        str: 去掉转义碎片、控制符和多余空白后的文本
    """
    if value is None:
        return ""

    original = str(value)
    if drop_if_corrupted and _looks_corrupted(original):
        return ""

    text = original
    # 把 LLM 输出的字面量换行符变成空格，避免邮箱前后出现 "\n"、"\r"。
    text = text.replace("\\n", " ").replace("\\r", " ").replace("\\t", " ")
    # 去掉真实控制符，防止字段保存进数据库后展示错乱。
    text = re.sub(r"[\r\n\t]+", " ", text)
    # 删除残缺 Unicode 代理对和字节转义碎片，这些通常无法恢复成可靠内容。
    text = re.sub(r"\\u[dD][0-9a-fA-F]{3}", "", text)
    text = re.sub(r"\\x[0-9a-fA-F]{2}", "", text)
    text = re.sub(r"(?:%[0-9a-fA-F]{2})+", "", text)
    # 删除 \C5D4 这类不合法转义片段，避免它们继续污染技能/项目字段。
    text = re.sub(r"\\[A-Za-z0-9]{2,8}", "", text)
    # 当前项目默认处理中英文简历；韩文混入多数来自模型乱码，因此清掉。
    text = re.sub(r"[\uac00-\ud7af]", "", text)
    # 删除实际代理字符、替换字符和 BOM。
    text = "".join(char for char in text if not (0xD800 <= ord(char) <= 0xDFFF))
    text = text.replace("\ufffd", "").replace("\ufeff", "")
    # 删除剩余反斜杠和包裹引号。
    text = text.replace("\\", "")
    text = text.strip(" \t\r\n\"'“”‘’")
    # 合并多余空白，让前端展示更稳定。
    text = re.sub(r"\s{2,}", " ", text).strip()

    if drop_if_corrupted and _looks_corrupted(text):
        return ""

    return text


def _clean_name(value: Any) -> str:
    """
    清洗候选人姓名。

    姓名字段比普通文本更严格，只保留中文、英文、空格和常见姓名连接符。
    """
    name = _clean_text(value, drop_if_corrupted=True)
    name = re.sub(r"[^A-Za-z\u4e00-\u9fff·.\-\s]", "", name)
    name = re.sub(r"\s{2,}", " ", name).strip()

    # 如果误把章节标题、职位或联系方式当成姓名，宁可置空并等待人工改名。
    # “个人概述”正是 PDF 简历中最常见的误判之一，因此明确拦截这类语义词。
    non_name_words = (
        r"邮箱|电话|手机|技能|项目|教育|工作|求职|简历|概述|简介|总结|"
        r"自我评价|基本信息|个人信息|联系方式|工程师|产品经理|实习生|岗位|职位"
    )
    if len(name) > 40 or _is_section_title(name) or re.search(non_name_words, name, flags=re.IGNORECASE):
        return ""
    return name


def _normalize_resume_lines(resume_text: str) -> List[str]:
    """
    把简历原文整理成非空行列表。

    前端文本框、PDF 和 DOCX 提取出来的换行风格可能不同，
    先统一清理，后面的规则解析才稳定。
    """
    return [
        _clean_text(line)
        for line in (resume_text or "").splitlines()
        if _clean_text(line)
    ]


def _extract_email(text: str) -> str:
    """
    从原始文本或脏字段中提取邮箱。

    邮箱是规则性很强的字段，用正则从原文抽取比让 LLM 生成更可靠。
    """
    match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text or "")
    return match.group(0).strip() if match else ""


def _extract_phone(text: str) -> str:
    """
    从原始文本中提取手机号。

    优先覆盖中国大陆手机号，同时允许 +86、空格和短横线。
    """
    match = re.search(r"(?:\+?86[-\s]?)?1[3-9]\d[-\s]?\d{4}[-\s]?\d{4}", text or "")
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(0)).strip()


def _extract_contact_info(resume_text: str) -> Dict[str, str]:
    """
    从简历原文确定性提取姓名、邮箱和电话。

    这些字段不应该依赖 LLM 猜测，因为它们一旦乱码会直接影响候选人列表。
    """
    text = resume_text or ""
    contact: Dict[str, str] = {
        "name": "",
        "email": _extract_email(text),
        "phone": _extract_phone(text),
    }

    # 优先匹配显式标签: 姓名: 张三 / Name: Tom。
    name_match = re.search(r"(?:姓名|名字|Name)\s*[:：]\s*([^\n\r,，;；|]{1,40})", text, flags=re.IGNORECASE)
    if name_match:
        contact["name"] = _clean_name(name_match.group(1))

    # 如果没有标签，从简历开头的联系方式区域找一个像姓名的短行。
    if not contact["name"]:
        for raw_line in _normalize_resume_lines(text)[:8]:
            # 带冒号的行通常是字段说明，不能整行当姓名。
            if ":" in raw_line or "：" in raw_line:
                continue
            if "|" in raw_line or _is_section_title(raw_line):
                continue
            line = _clean_name(raw_line)
            # 中文姓名通常 2-6 个汉字，英文姓名通常是 2-4 个单词。
            looks_like_chinese_name = bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", line))
            looks_like_english_name = bool(re.fullmatch(r"[A-Za-z]+(?:[ .-][A-Za-z]+){1,3}", line))
            if (
                (looks_like_chinese_name or looks_like_english_name)
                and line
                and "@" not in raw_line
                and not _extract_phone(raw_line)
            ):
                contact["name"] = line
                break

    return contact


def _split_resume_sections(resume_text: str) -> Dict[str, List[str]]:
    """
    按常见中文简历标题切分原文。

    这样可以在 LLM 结构化输出不稳定时，从原文稳定抽取教育、项目、技能等字段。
    """
    sections: Dict[str, List[str]] = {"_header": []}
    current = "_header"
    for line in _normalize_resume_lines(resume_text):
        if _is_section_title(line):
            current = line
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _parse_date_range(line: str) -> tuple[int | None, int | None]:
    """
    从一行时间文本里提取开始年份和结束年份。

    例如 "2025.02 - 2026.12" 会得到 (2025, 2026)。
    """
    years = [int(year) for year in re.findall(r"(?:19|20)\d{2}", line or "")]
    if not years:
        return None, None
    if len(years) == 1:
        return years[0], None
    return years[0], years[-1]


def _is_date_line(line: str) -> bool:
    """判断一行是否主要表示时间范围。"""
    return bool(re.search(r"(?:19|20)\d{2}[./年-]?", line or ""))


def _extract_education_from_text(sections: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    """
    从“教育经历”段落抽取教育信息。

    规则按中文简历常见写法设计: 学校名、专业/学位、时间范围三行一组。
    """
    lines = sections.get("教育经历", [])
    education: List[Dict[str, Any]] = []
    index = 0
    while index < len(lines):
        school = _clean_text(lines[index], drop_if_corrupted=True)
        if not school or _is_date_line(school):
            index += 1
            continue

        major_degree = _clean_text(lines[index + 1], drop_if_corrupted=True) if index + 1 < len(lines) else ""
        date_line = _clean_text(lines[index + 2], drop_if_corrupted=True) if index + 2 < len(lines) else ""
        if not _is_date_line(date_line):
            index += 1
            continue

        degree = ""
        for degree_word in ["博士", "硕士", "本科", "学士", "研究生"]:
            if degree_word in major_degree:
                degree = "学士" if degree_word == "本科" else degree_word
                break
        major = major_degree
        for degree_word in ["博士", "硕士", "本科", "学士", "研究生"]:
            major = major.replace(degree_word, "")
        start_year, end_year = _parse_date_range(date_line)
        education.append({
            "degree": degree,
            "school": school,
            "major": major.strip(),
            "start_year": start_year,
            "end_year": end_year,
        })
        index += 3
    return education


def _extract_skills_from_text(sections: Dict[str, List[str]]) -> List[str]:
    """
    从“技能/专业技能”段落抽取技能关键词。

    保留冒号后的具体技能，并按顿号、圆点和逗号切分。
    """
    lines = sections.get("技能", []) + sections.get("专业技能", [])
    skills: List[str] = []
    seen = set()
    for line in lines:
        content = re.split(r"[:：]", line, maxsplit=1)[-1]
        parts = re.split(r"[·、,，/]+", content)
        for part in parts:
            skill = _clean_text(part, drop_if_corrupted=True)
            if skill and skill not in seen:
                skills.append(skill)
                seen.add(skill)
    return skills


def _extract_technologies(text: str) -> List[str]:
    """
    从项目描述中识别常见技术词。

    这不是为了穷举所有技术，而是给项目卡片一个稳定、干净的 technologies 字段。
    """
    technologies: List[str] = []
    lower_text = text.lower()
    for keyword in TECH_KEYWORDS:
        if keyword.lower() in lower_text and keyword not in technologies:
            technologies.append(keyword)
    return technologies


def _extract_projects_from_text(sections: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    """
    从“项目经历”段落抽取项目。

    常见格式是: 项目名、时间、若干描述。遇到下一组“项目名+时间”时切换项目。
    """
    lines = sections.get("项目经历", [])
    projects: List[Dict[str, Any]] = []
    index = 0
    while index < len(lines):
        name = _clean_text(lines[index], drop_if_corrupted=True)
        if not name or _is_date_line(name):
            index += 1
            continue
        if index + 1 >= len(lines) or not _is_date_line(lines[index + 1]):
            index += 1
            continue

        start = index + 2
        end = start
        while end < len(lines):
            next_line = lines[end]
            next_has_date = end + 1 < len(lines) and _is_date_line(lines[end + 1])
            if next_has_date and not _is_date_line(next_line):
                break
            end += 1

        description_lines = [_clean_text(line, drop_if_corrupted=True) for line in lines[start:end]]
        description_lines = [line for line in description_lines if line]
        description = "\n".join(description_lines)
        projects.append({
            "name": name,
            "description": description,
            "technologies": _extract_technologies(" ".join([name, description])),
            "role": None,
        })
        index = end
    return projects


def _extract_work_from_text(sections: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    """
    从“实习经历/工作经历”段落抽取工作经历。

    常见格式是: 公司、职位、时间、若干描述。
    """
    lines = sections.get("实习经历", []) + sections.get("工作经历", [])
    work_items: List[Dict[str, Any]] = []
    index = 0
    while index < len(lines):
        if index + 2 >= len(lines):
            break
        company = _clean_text(lines[index], drop_if_corrupted=True)
        title = _clean_text(lines[index + 1], drop_if_corrupted=True)
        duration = _clean_text(lines[index + 2], drop_if_corrupted=True)
        if not company or not title or not _is_date_line(duration):
            index += 1
            continue

        start = index + 3
        end = start
        while end < len(lines):
            next_group = end + 2 < len(lines) and _is_date_line(lines[end + 2])
            if next_group:
                break
            end += 1
        description = _clean_string_list(lines[start:end])
        work_items.append({
            "company": company,
            "title": title,
            "duration": duration,
            "description": description,
        })
        index = end
    return work_items


def _clean_string_list(values: Any) -> List[str]:
    """
    清洗字符串列表，并去重。

    技能、证书、优势、风险点都走这个函数，避免列表里残留乱码项。
    """
    if not isinstance(values, list):
        return []

    cleaned_items: List[str] = []
    seen = set()
    for item in values:
        cleaned = _clean_text(item, drop_if_corrupted=True)
        if cleaned and cleaned not in seen:
            cleaned_items.append(cleaned)
            seen.add(cleaned)
    return cleaned_items


def _clean_year(value: Any) -> int | None:
    """
    把年份字段整理成整数。

    LLM 偶尔会输出 "—" 或空字符串，这些值不能直接进入年份字段。
    """
    if value in (None, "", "—", "-"):
        return None
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    return year if 1900 <= year <= 2100 else None


def _sanitize_profile(profile: Dict[str, Any], resume_text: str) -> Dict[str, Any]:
    """
    清洗 Resume Agent 的完整输出。

    这层相当于后端安全网: LLM 负责理解，后处理负责把明显不可信的字段挡住。
    """
    contact = _extract_contact_info(resume_text)
    sections = _split_resume_sections(resume_text)
    text_education = _extract_education_from_text(sections)
    text_skills = _extract_skills_from_text(sections)
    text_projects = _extract_projects_from_text(sections)
    text_work_experience = _extract_work_from_text(sections)
    llm_skills = _clean_string_list(profile.get("skills"))

    sanitized: Dict[str, Any] = {
        "candidate_id": profile.get("candidate_id", ""),
        "name": contact["name"] or _clean_name(profile.get("name")),
        "email": contact["email"] or _extract_email(_clean_text(profile.get("email"))),
        "phone": contact["phone"] or _clean_text(profile.get("phone"), drop_if_corrupted=True),
        "education": text_education.copy(),
        "skills": [],
        "projects": text_projects.copy(),
        "work_experience": text_work_experience.copy(),
        "certifications": _clean_string_list(profile.get("certifications")),
        "strengths": _clean_string_list(profile.get("strengths")),
        "risks": _clean_string_list(profile.get("risks")),
        "missing_info": _clean_string_list(profile.get("missing_info")),
        "estimated_years_of_experience": profile.get("estimated_years_of_experience"),
    }

    # 技能优先使用原文技能段落，再用 LLM 的干净技能补漏。
    seen_skills = set()
    for skill in text_skills + llm_skills:
        if skill and skill not in seen_skills:
            sanitized["skills"].append(skill)
            seen_skills.add(skill)

    # 如果原文没有教育段落，再使用 LLM 的干净教育结果。
    if not sanitized["education"]:
        for item in profile.get("education") or []:
            if not isinstance(item, dict):
                continue
            cleaned = {
                "degree": _clean_text(item.get("degree"), drop_if_corrupted=True),
                "school": _clean_text(item.get("school"), drop_if_corrupted=True),
                "major": _clean_text(item.get("major"), drop_if_corrupted=True),
                "start_year": _clean_year(item.get("start_year")),
                "end_year": _clean_year(item.get("end_year")),
            }
            if cleaned["degree"] or cleaned["school"] or cleaned["major"]:
                sanitized["education"].append(cleaned)

    # 如果原文没有项目段落，再使用 LLM 的干净项目结果。
    if not sanitized["projects"]:
        for item in profile.get("projects") or []:
            if not isinstance(item, dict):
                continue
            cleaned = {
                "name": _clean_text(item.get("name"), drop_if_corrupted=True),
                "description": _clean_text(item.get("description"), drop_if_corrupted=True),
                "technologies": _clean_string_list(item.get("technologies")),
                "role": _clean_text(item.get("role"), drop_if_corrupted=True) or None,
            }
            if cleaned["name"] or cleaned["description"] or cleaned["technologies"]:
                sanitized["projects"].append(cleaned)

    # 如果原文没有实习/工作段落，再使用 LLM 的干净工作经历结果。
    if not sanitized["work_experience"]:
        for item in profile.get("work_experience") or []:
            if not isinstance(item, dict):
                continue
            cleaned = {
                "company": _clean_text(item.get("company"), drop_if_corrupted=True),
                "title": _clean_text(item.get("title"), drop_if_corrupted=True),
                "duration": _clean_text(item.get("duration"), drop_if_corrupted=True) or None,
                "description": _clean_string_list(item.get("description")),
            }
            if cleaned["company"] or cleaned["title"] or cleaned["description"]:
                sanitized["work_experience"].append(cleaned)

    years = sanitized["estimated_years_of_experience"]
    if years in ("", "—", "-"):
        sanitized["estimated_years_of_experience"] = None

    return sanitized


async def parse_resume(
    resume_text: str,
    candidate_id: str,
) -> Dict[str, Any]:
    """
    解析单份简历，提取候选人结构化画像。

    这个方法做的事:
    1. 读取简历纯文本 (由 document_loader 提前提取)
    2. 调用 LLM 提取结构化信息 (教育、技能、项目、经历)
    3. 让 LLM 分析候选人优势和风险点
    4. 识别简历中缺失的关键信息

    参数:
        resume_text: 从 PDF/DOCX 文件中提取的纯文本
        candidate_id: 系统生成的候选人唯一ID
    返回:
        dict: 符合 CandidateProfile schema 的字典
    """
    # 构造系统提示词
    # 详细告诉 LLM 每个字段应该提取什么
    system_prompt = """你是一位资深 HR，输出必须使用中文。

【语言要求 - 最高优先级】
所有文字输出必须是中文。具体规则:
- 技能名称: "Machine Learning"→"机器学习", 但 Python/Docker 保留原样
- 学位: "Bachelor"→"学士", "Master"→"硕士", "PhD"→"博士"
- 项目描述、工作内容、优势、风险点: 全部用中文
- 专有名词保留原文: 学校名(MIT)、公司名(Google)、技术术语(Docker, RAG)

【提取规则】
1. 姓名(name): 从简历头部提取
2. 邮箱(email): 提取邮箱地址
3. 教育经历(education): degree(学位,中文)/school(学校,原文)/major(专业,中文)
4. 技能(skills): 技术技能列表, 中文描述+原文保留
5. 项目经历(projects): name(原文)/description(中文)/technologies(原文)
6. 工作经历(work_experience): company(原文)/title(中文)/description(中文)
7. 证书(certifications): 专业证书
8. 优势(strengths): 用中文总结候选人亮点
9. 风险点(risks): 用中文指出潜在问题
10. 缺失信息(missing_info): 用中文列出缺失项

【重要】
- 找不到的用空列表[], 不要编造
- 姓名、邮箱、电话必须逐字从原文复制，不要猜测、不要翻译
- 不要输出任何 \\uXXXX、\\xHH、乱码、Emoji 或无法确认来源的字符
- 教育/项目使用嵌套对象格式
- 经验年限从工作经历推算, 无数据则 null"""

    # 调用 LLM 进行结构化提取
    candidate_profile = await call_llm_structured(
        system_prompt=system_prompt,
        user_message=f"请解析以下候选人简历:\n\n{resume_text}",
        output_schema=CandidateProfile,
    )

    # 转换为字典 + 修复 Unicode + 附加 candidate_id
    from app.services.llm_service import _fix_unicode_strings
    profile_dict = _fix_unicode_strings(candidate_profile.model_dump())
    profile_dict["candidate_id"] = candidate_id
    profile_dict = _sanitize_profile(profile_dict, resume_text)
    profile_dict["candidate_id"] = candidate_id

    return profile_dict


async def batch_parse_resumes(
    resume_texts: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    批量解析多份简历。

    遍历每份简历，逐个调用 parse_resume() 解析。

    参数:
        resume_texts: {candidate_id: resume_text} 的字典
    返回:
        List[dict]: 所有候选人画像的列表
    """
    import asyncio

    # 并行解析所有简历
    async def parse_one(cid, text):
        return await parse_resume(resume_text=text, candidate_id=cid)

    profiles = await asyncio.gather(
        *[parse_one(cid, text) for cid, text in resume_texts.items()]
    )

    return list(profiles)
