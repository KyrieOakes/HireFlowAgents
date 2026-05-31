"""
app/services/llm_service.py
=============================
LLM 调用服务 (Local + Cloud 双模式)。

支持两种运行模式，通过 settings.llm.mode 切换:
- "local": 连接本地 LM Studio (http://localhost:1234/v1)
- "cloud": 连接 DeepSeek API (https://api.deepseek.com)

两者都是 OpenAI 兼容接口，底层使用同一个 ChatOpenAI 类，
切换只需改变 base_url 和 api_key，代码逻辑完全不变。

结构化输出使用 LangChain 的 with_structured_output() 方法:
- 传入 Pydantic Model 类
- LangChain 自动生成 JSON Schema 并注入到 prompt
- 返回值直接是 Pydantic 实例，自动验证格式
"""

from typing import Dict, Any, Type
from langchain_openai import ChatOpenAI
from app.utils.config import settings


def _get_llm() -> ChatOpenAI:
    """
    根据配置创建 ChatOpenAI 实例 (支持本地/云端自动切换)。

    ChatOpenAI 是 LangChain 封装的 OpenAI 兼容客户端。
    只要目标服务实现了 OpenAI 兼容 API (LM Studio 和 DeepSeek 都实现了)，
    就可以用同一个类来调用。

    返回:
        ChatOpenAI: 配置好的 LLM 客户端
    """
    # 获取 LLM 配置
    llm_config = settings.llm

    # 根据 mode 决定使用哪套配置
    if llm_config.mode == "local":
        # 本地 LM Studio 模式
        # LM Studio 不需要真实 API Key，填任意值即可
        base_url = llm_config.local_base_url
        api_key = llm_config.local_api_key
        model = llm_config.local_model
    else:
        # 云端 DeepSeek 模式
        base_url = llm_config.cloud_base_url
        api_key = llm_config.cloud_api_key
        model = llm_config.cloud_model

    # 创建 ChatOpenAI 实例
    # temperature: 输出随机性，招聘场景用低值保证稳定输出
    return ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=model,
        temperature=llm_config.temperature,
    )


def call_llm(
    system_prompt: str,
    user_message: str,
) -> str:
    """
    调用 LLM 进行自由文本对话。

    适用场景: 不需要结构化输出的任务，如生成排序解释、邮件正文等。

    参数:
        system_prompt: 系统提示词，定义 LLM 的角色和行为规则
                       例如: "你是一位资深招聘专家..."
        user_message: 用户消息，即需要 LLM 处理的具体内容
    返回:
        str: LLM 返回的文本响应
    """
    # 获取 LLM 客户端
    llm = _get_llm()

    # 构造消息列表
    # SystemMessage: 设定 AI 的角色和行为
    # HumanMessage: 用户的实际问题
    from langchain_core.messages import SystemMessage, HumanMessage
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]

    # 调用 LLM
    # invoke() 发送消息并等待完整响应返回
    response = llm.invoke(messages)

    # .content 是 LLM 返回的纯文本内容
    return response.content


def call_llm_structured(
    system_prompt: str,
    user_message: str,
    output_schema: Type,
) -> Any:
    """
    调用 LLM 并返回结构化 JSON 响应。

    使用 LangChain 的 with_structured_output() 方法:
    1. 传入 Pydantic Model 类 (如 JobDescription)
    2. LangChain 自动将 Model 的字段定义转为 JSON Schema
    3. 注入 prompt，告诉 LLM 必须按这个格式输出
    4. LLM 返回后自动用 Pydantic 验证
    5. 如果格式不正确，LangChain 内置重试机制

    这是整个项目中最重要的 LLM 调用方式。
    所有 Agent 的结构化输出都通过这个函数完成。

    参数:
        system_prompt: 系统提示词
        user_message: 用户消息 (通常包含要解析的原始文本)
        output_schema: Pydantic 模型类，约束 LLM 的输出格式
                       例如: call_llm_structured(prompt, text, output_schema=JobDescription)
    返回:
        Pydantic Model 实例: 已验证的结构化数据
                             例如: JobDescription(job_title="AI Engineer", ...)
    """
    # 获取 LLM 客户端
    llm = _get_llm()

    # 关键步骤: with_structured_output()
    # 这个方法告诉 LangChain: "这个 LLM 的输出必须符合 output_schema 的格式"
    # method="function_calling" 使用 OpenAI 的 tool_choice 机制约束输出
    structured_llm = llm.with_structured_output(
        output_schema,
        method="function_calling",
    )

    # 构造消息
    from langchain_core.messages import SystemMessage, HumanMessage
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]

    # 调用并获取已验证的结构化结果
    # 返回值直接是 Pydantic 实例，例如 JobDescription 对象
    result = structured_llm.invoke(messages)

    return result
