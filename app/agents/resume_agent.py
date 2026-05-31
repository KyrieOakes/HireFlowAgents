"""
app/agents/resume_agent.py
===========================
Resume Agent: 简历解析 Agent。

职责: 从原始简历文本中提取候选人结构化画像。
这是招聘流程的第二个 Agent，每个候选人都需要经过它处理。

输入: 简历文本 (从 PDF/DOCX 提取后的纯文本)
输出: 候选人画像 JSON (state.candidate_profiles)
"""

from typing import Dict, Any, List


async def parse_resume(
    resume_text: str,
    candidate_id: str,
    llm_service,
) -> Dict[str, Any]:
    """
    解析单份简历，提取候选人结构化画像。

    这个函数做的事:
    1. 读取简历纯文本
    2. 调用 LLM 提取结构化信息
    3. 分析候选人优势和风险点
    4. 识别缺失信息

    参数:
        resume_text: 从简历文件中提取的纯文本
        candidate_id: 系统生成的候选人唯一 ID
        llm_service: LLM 调用服务
    返回:
        dict: 符合 resume_schema.CandidateProfile 格式的结构化数据
    """
    # TODO: 实现简历解析逻辑
    # 1. 构造 system prompt (角色: 资深 HR/猎头)
    # 2. 传入 resume_text 作为 user message
    # 3. 使用 call_llm_structured() 约束输出为 CandidateProfile schema
    # 4. 错误处理: 如果 PDF 解析出的文本太乱，尝试不同策略
    # 5. 返回验证后的候选人画像

    # 重要的解析技巧:
    # - 简历格式千差万别，LLM 需要有一定的"容错能力"
    # - 如果某个字段解析不出来，标注为缺失而不是编造
    # - 注意区分"项目经历"和"工作经历"
    pass


async def batch_parse_resumes(
    resume_files: List[str],
    llm_service,
) -> List[Dict[str, Any]]:
    """
    批量解析多份简历。

    参数:
        resume_files: 简历文件路径列表
        llm_service: LLM 调用服务
    返回:
        List[dict]: 所有候选人画像的列表
    """
    # TODO: 实现批量解析
    # 1. 遍历 resume_files
    # 2. 对每个文件:
    #    a. 调用 document_loader 提取文本
    #    b. 生成 candidate_id (如 "C001", "C002"...)
    #    c. 调用 parse_resume() 解析
    # 3. 收集所有结果到列表
    # 4. 返回候选人画像列表
    pass
