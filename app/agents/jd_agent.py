"""
app/agents/jd_agent.py
=======================
JD Agent: 岗位描述分析 Agent。

职责: 从原始岗位描述文本中提取结构化信息。
这是招聘流程的第一个 Agent，它的输出是整个流程的基准。

输入: 原始岗位描述文本 (state.jd_text)
输出: 结构化岗位信息 JSON (state.jd_profile)
"""

from typing import Dict, Any


async def analyze_jd(jd_text: str, llm_service) -> Dict[str, Any]:
    """
    分析岗位描述文本，提取结构化岗位需求。

    这个函数做的事:
    1. 读取非结构化的岗位描述原始文本
    2. 调用 LLM 提取关键信息 (岗位名、技能、职责等)
    3. 生成评分 Rubric (各维度的权重)
    4. 用 Pydantic schema 验证输出格式

    参数:
        jd_text: 用户上传的原始岗位描述全文
        llm_service: LLM 调用服务 (依赖注入，方便测试时替换)
    返回:
        dict: 符合 jd_schema.JobDescription 格式的结构化数据
    """
    # TODO: 实现 JD 分析逻辑
    # 1. 构造 system prompt，告诉 LLM 它是招聘专家
    # 2. 把 jd_text 作为 user message 传给 LLM
    # 3. 使用 call_llm_structured() 约束输出为 JobDescription schema
    # 4. 如果 LLM 返回格式错误，重试 (最多 3 次)
    # 5. 返回验证后的字典

    # 示例 system prompt:
    # system_prompt = """
    # 你是一位资深的招聘专家和技术面试官。
    # 你的任务是从岗位描述(JD)中提取结构化的信息。
    # 请仔细阅读 JD 并提取:
    # - 岗位名称
    # - 必备技能: 候选人必须掌握的技能
    # - 加分技能: 候选人掌握会更好但不是必须的技能
    # ...
    # """
    pass


def build_rubric(jd_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    根据岗位需求构建评分 Rubric。

    评分 Rubric 定义了 Match Agent 评分的各维度权重。
    不同岗位可能侧重不同的维度 (如技术岗重技能，管理岗重经验)。

    参数:
        jd_profile: JD Agent 解析出的结构化岗位信息
    返回:
        dict: 评分 Rubric，格式见 jd_schema.ScoringRubric
    """
    # TODO: 实现 Rubric 构建
    # 1. 根据岗位类型调整权重
    #    例如: 技术岗 -> technical_skills 权重提高
    #          管理岗 -> experience 权重提高
    # 2. 确保所有权重之和 = 100
    pass
