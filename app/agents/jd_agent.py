"""
app/agents/jd_agent.py
=======================
JD Agent: 岗位描述分析 Agent。

职责: 读取原始岗位描述文本，调用 LLM 提取结构化信息。
这是整个招聘流程的起点，输出作为后续匹配的基准。

输入: 原始岗位描述文本 (字符串)
输出: JobDescription Pydantic 对象 + ScoringRubric 字典
"""

from typing import Dict, Any
from app.services.llm_service import call_llm_structured, call_llm
from app.schemas.jd_schema import JobDescription
from app.utils.config import settings


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

    # ================================================================
    # 第2步: 生成评分 Rubric
    # ================================================================
    rubric = _generate_rubric(jd_dict)

    # 将 rubric 附加到 jd_dict 中一起返回
    jd_dict["rubric"] = rubric

    return jd_dict


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
