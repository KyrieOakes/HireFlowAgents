"""
app/services/llm_service.py
=============================
LLM 调用服务。

封装对大型语言模型的调用，提供统一的接口。
所有 Agent 都通过这个服务来调用 LLM。

技术选型:
- OpenAI API (GPT-4o, GPT-4o-mini)
- 或 Anthropic Claude API
- 通过统一接口方便切换模型
"""

from typing import Dict, Any


def call_llm(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.1,
) -> str:
    """
    调用 LLM 并返回文本响应。

    参数:
        system_prompt: 系统提示词，定义 LLM 的角色和行为规则
        user_message: 用户消息，即实际要处理的内容
        temperature: 输出随机性 (0=确定性, 1=创造性)
                     招聘场景建议用较低值 (0.1) 以保证输出稳定性
    返回:
        str: LLM 的文本响应
    """
    # TODO: 实现 LLM 调用
    # 1. 配置 API Key (从环境变量读取)
    # 2. 构造请求消息
    # 3. 调用 LLM API
    # 4. 返回响应内容
    pass


def call_llm_structured(
    system_prompt: str,
    user_message: str,
    output_schema: type,
    temperature: float = 0.1,
) -> Dict[str, Any]:
    """
    调用 LLM 并返回结构化 JSON 响应。

    使用 Pydantic schema 约束 LLM 的输出格式。
    这是 Information Extraction 层的核心调用方式。

    参数:
        system_prompt: 系统提示词
        user_message: 用户消息
        output_schema: Pydantic 模型类，用于约束输出格式
                       例如: call_llm_structured(..., output_schema=JobDescription)
        temperature: 输出随机性
    返回:
        dict: 符合 output_schema 定义的字典
    """
    # TODO: 实现结构化 LLM 调用
    # 1. 将 Pydantic schema 转换为 JSON Schema
    # 2. 使用 function calling 或 structured output 模式
    # 3. 验证返回的 JSON 是否符合 schema
    # 4. 返回验证后的字典
    pass
