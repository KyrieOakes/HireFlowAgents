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
    system_prompt = """你是一位资深的 HR 和猎头顾问，拥有丰富的简历筛选经验。
你的任务是从候选人简历中提取结构化的信息。

提取规则:
1. 姓名(name): 从简历头部提取候选人姓名
2. 邮箱(email): 提取邮箱地址
3. 电话(phone): 提取电话号码(如果有)
4. 教育经历(education): 每条教育经历提取 degree(学位)、school(学校)、major(专业)、时间
5. 技能(skills): 列出所有技术技能，如编程语言、框架、工具、平台等
6. 项目经历(projects): 每个项目提取 name(名称)、description(描述)、technologies(使用的技术)
7. 工作/实习经历(work_experience): 每个经历提取 company(公司)、title(职位)、duration(时间)、description(内容)
8. 证书(certifications): 列出专业证书
9. 优势(strengths): 分析候选人的亮点，如匹配的技术栈、优秀的项目经验等
10. 风险点(risks): 识别潜在问题，如经验不足、技能缺口、频繁跳槽、经历断层等
11. 缺失信息(missing_info): 简历中没有提及但对招聘决策重要的信息

重要:
- 如果某个字段在简历中找不到，用空列表[]表示，不要编造
- 教育经历和项目经历使用嵌套对象格式 (参考输出格式示例)
- 优势和风险点要具体，不要泛泛而谈
- estimated_years_of_experience 从工作经历中推算，如果无法推算则设为 null"""

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
    profiles = []

    for candidate_id, resume_text in resume_texts.items():
        # 调用 parse_resume 解析单份简历
        profile = await parse_resume(
            resume_text=resume_text,
            candidate_id=candidate_id,
        )
        profiles.append(profile)

    return profiles
