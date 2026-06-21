"""
app/graph/state.py
==================
LangGraph 全局共享状态定义。

HiringState 是整个工作流的"数据总线"。
每个 Agent 节点只负责读写自己对应的字段，
所有节点通过这个共享字典传递数据。

LangGraph 的 StateGraph 会在每个节点执行后自动合并返回的字典。
"""

from typing import List, Dict, Any, TypedDict


class HiringState(TypedDict):
    """
    招聘工作流的全局共享状态。

    每个字段对应工作流中某一阶段产生的数据。
    TypedDict 是 Python 类型提示的一种，用于定义字典的键和值的类型。
    这个类型定义让 IDE 可以给出自动补全提示，也能在运行时做类型检查。
    """

    # ---- 岗位相关 ----
    # job_id: 岗位的唯一标识符 (字符串)
    job_id: str
    # jd_text: 用户上传的原始岗位描述全文
    jd_text: str
    # jd_profile: JD Agent 解析后的结构化岗位信息 (JSON 字典)
    jd_profile: Dict[str, Any]

    # ---- 简历相关 ----
    # resume_texts: 上传的简历文本列表, 每个元素包含 candidate_id, text, filename
    # 格式: [{"candidate_id": "xxx", "text": "简历全文...", "filename": "xxx.pdf"}, ...]
    resume_texts: List[Dict[str, str]]
    # candidate_profiles: Resume Agent 解析后的候选人信息列表
    candidate_profiles: List[Dict[str, Any]]

    # ---- RAG 检索相关 ----
    # resume_chunks: 简历文本切分后的 chunk 列表，每个 chunk 包含文本和来源页码
    resume_chunks: List[Dict[str, Any]]
    # retrieved_evidence: 检索到的证据，key 是候选人 ID，value 是该候选人的证据列表
    retrieved_evidence: Dict[str, List[Dict[str, Any]]]

    # ---- 匹配和排序 ----
    # match_results: Match Agent 对每个候选人的评分结果列表
    match_results: List[Dict[str, Any]]
    # ranking_results: Ranking Agent 排序后的候选人列表
    ranking_results: List[Dict[str, Any]]

    # ---- 面试相关 ----
    # selected_candidate_ids: 人工审核后选中的候选人 ID 列表
    selected_candidate_ids: List[str]
    # interview_questions: 面试问题，key 是候选人 ID，value 是该候选人的问题列表
    interview_questions: Dict[str, List[Dict[str, Any]]]

    # ---- 面试评价 ----
    # interview_feedback: 面试反馈文本，key 是候选人 ID，value 是反馈文字
    interview_feedback: Dict[str, str]
    # final_evaluations: 最终评价结果，key 是候选人 ID，value 是结构化评价
    final_evaluations: Dict[str, Dict[str, Any]]

    # ---- 邮件 ----
    # email_drafts: 邮件草稿，key 是类型(如 "invite"/"reject")，value 包含标题和正文
    email_drafts: Dict[str, Dict[str, str]]

    # ---- 流程控制 ----
    # human_review_status: 人工审核状态 ("pending"/"approved"/"rejected")
    human_review_status: str
    # errors: 流程中收集的错误信息列表
    errors: List[str]
