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

from typing import Dict, Any, List
from app.services.llm_service import call_llm_structured
from app.schemas.resume_schema import CandidateProfile
from app.utils.config import settings


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
- 教育/项目使用嵌套对象格式
- 经验年限从工作经历推算, 无数据则 null"""

    # 调用 LLM 进行结构化提取
    candidate_profile = call_llm_structured(
        system_prompt=system_prompt,
        user_message=f"请解析以下候选人简历:\n\n{resume_text}",
        output_schema=CandidateProfile,
    )

    # 转换为字典并附加 candidate_id
    profile_dict = candidate_profile.model_dump()
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
