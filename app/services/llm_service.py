"""
app/services/llm_service.py
=============================
LLM 调用服务 (Local + Cloud 双模式)。

支持两种运行模式，通过 settings.llm.mode 切换:
- "local": LM Studio hermes-3-llama-3.1-8b
- "cloud": DeepSeek API deepseek-v4-pro

结构化输出策略:
- 本地 (hermes-3): LangChain with_structured_output(method="json_schema")
- 云端 (deepseek-v4-pro): LangChain with_structured_output(method="function_calling")
  注意: DeepSeek thinking 模式下不支持 function_calling，需要传入 thinking=disabled

所有 Agent 共用同一个模型，通过不同的 system_prompt 实现不同职责。
"""

from typing import Any, Type
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel
from app.utils.config import settings


def _get_llm() -> ChatOpenAI:
    """
    根据配置创建 ChatOpenAI 实例。

    返回:
        ChatOpenAI: 配置好的 LLM 客户端
    """
    llm_config = settings.llm

    if llm_config.mode == "local":
        base_url = llm_config.local_base_url
        api_key = llm_config.local_api_key
        model = llm_config.local_model
    else:
        base_url = llm_config.cloud_base_url
        api_key = llm_config.cloud_api_key
        model = llm_config.cloud_model

    # 基础参数
    kwargs = dict(
        base_url=base_url,
        api_key=api_key,
        model=model,
        temperature=llm_config.temperature,
        max_tokens=llm_config.max_tokens,
    )

    # DeepSeek: function_calling 需要关闭 thinking
    if llm_config.mode == "cloud":
        # LangChain ChatOpenAI 的 extra_body 参数会直接传给 OpenAI SDK
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

    return ChatOpenAI(**kwargs)


def call_llm(
    system_prompt: str,
    user_message: str,
) -> str:
    """
    调用 LLM 进行自由文本对话。

    适用场景: 生成排序解释、邮件正文等不需要结构化输出的任务。

    参数:
        system_prompt: 系统提示词
        user_message: 用户消息
    返回:
        str: LLM 的文本响应
    """
    llm = _get_llm()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]
    response = llm.invoke(messages)
    return response.content


def call_llm_structured(
    system_prompt: str,
    user_message: str,
    output_schema: Type[BaseModel],
) -> Any:
    """
    调用 LLM 并返回结构化 Pydantic 响应。

    根据 mode 自动选择最佳方式:
    - local (hermes-3): json_schema (模型原生支持 response_format json_schema)
    - cloud (deepseek-v4-pro): function_calling (已在 _get_llm 中禁用 thinking)

    参数:
        system_prompt: 系统提示词
        user_message: 用户消息
        output_schema: Pydantic 模型类
    返回:
        Pydantic Model 实例
    """
    llm = _get_llm()

    # 根据模式选择结构化输出方法
    if settings.llm.mode == "local":
        # hermes-3-llama-3.1-8b 支持 response_format json_schema
        method = "json_schema"
    else:
        # deepseek-v4-pro: thinking 已禁用，可用 function_calling
        method = "function_calling"

    structured_llm = llm.with_structured_output(output_schema, method=method)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]

    return structured_llm.invoke(messages)


# ================================================================
# JSON 解析工具: 健壮地从 LLM 响应中提取 JSON
# ================================================================

def parse_json_response(raw: str, default: dict = None) -> dict:
    """
    从 LLM 自由文本响应中提取 JSON 对象。

    LLM 可能返回:
    - 纯 JSON: {"key": "value"}
    - Markdown 代码块: ```json\n{...}\n```
    - 带前缀文本: 好的，这是结果: {...}
    - 嵌套在文字中

    这个函数尝试多种策略提取 JSON, 比直接 json.loads() 更健壮。

    参数:
        raw: LLM 原始响应文本
        default: 解析全部失败时的默认值
    返回:
        dict: 解析出的 JSON 对象
    """
    import json, re

    if default is None:
        default = {}

    text = raw.strip()

    # 策略 1: 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 策略 2: 去掉 markdown 代码块标记
    # ```json\n{...}\n``` 或 ```\n{...}\n```
    cleaned = re.sub(r'^```(?:json)?\s*\n', '', text)
    cleaned = re.sub(r'\n```\s*$', '', cleaned)
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError:
        pass

    # 策略 3: 找第一个 { 和最后一个 } 之间的内容 (对象)
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and start < end:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    # 策略 4: 找第一个 [ 和最后一个 ] 之间的内容 (数组)
    start = text.find('[')
    end = text.rfind(']')
    if start != -1 and end != -1 and start < end:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    # 全部失败, 返回默认值
    return default
