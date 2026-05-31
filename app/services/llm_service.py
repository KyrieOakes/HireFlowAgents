"""
app/services/llm_service.py
=============================
LLM 调用服务 (Local + Cloud 双模式)。

支持两种运行模式，通过 settings.llm.mode 切换:
- "local": 连接本地 LM Studio (qwen3-8b-mlx)
- "cloud": 连接 DeepSeek API

两者都是 OpenAI 兼容接口，底层使用同一个 ChatOpenAI 类。

结构化输出策略:
- 云端 (DeepSeek): 使用 LangChain with_structured_output(function_calling)
- 本地 (qwen3): 使用 prompt-injection 方式 (将 JSON Schema 注入 prompt)
  因为 qwen3-8b-mlx 不支持 tool_choice 参数

所有 Agent 共用同一个模型 (qwen3-8b-mlx)，通过不同的 system_prompt 实现不同职责。
"""

import json
from typing import Dict, Any, Type
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from pydantic import BaseModel
from app.utils.config import settings


def _get_llm() -> ChatOpenAI:
    """
    根据配置创建 ChatOpenAI 实例 (支持本地/云端自动切换)。

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

    return ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=model,
        temperature=llm_config.temperature,
        max_tokens=llm_config.max_tokens,
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
        user_message: 用户消息，即需要 LLM 处理的具体内容
    返回:
        str: LLM 返回的文本响应
    """
    llm = _get_llm()

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]

    response = llm.invoke(messages)
    return response.content


def _generate_json_schema(schema_class: Type[BaseModel]) -> str:
    """
    将 Pydantic Model 转换为 JSON 示例 + 字段说明，用于注入 prompt。

    对于本地模型 (qwen3-8b-mlx)，需要提供非常具体的 JSON 示例。
    模型看到示例后，会模仿其结构输出。

    参数:
        schema_class: Pydantic 模型类
    返回:
        str: 包含 JSON 示例和字段说明的文本
    """
    schema = schema_class.model_json_schema()
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    # 生成字段说明表
    lines = ["请严格按照以下 JSON 格式输出，不要输出任何其他内容:"]
    lines.append("")
    lines.append("字段说明 (注意区分嵌套对象的子字段):")
    lines.append("")

    _describe_properties(properties, required, lines, indent=0)

    # 生成 JSON 示例 (关键: 展示嵌套结构)
    lines.append("")
    lines.append("JSON 示例 (请严格模仿此结构):")
    lines.append("```")
    example = _build_example(schema_class)
    lines.append(json.dumps(example, ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("只输出 JSON，不要加解释或 markdown 标记。")

    return "\n".join(lines)


def _describe_properties(
    properties: dict,
    required: set,
    lines: list,
    indent: int,
):
    """
    递归描述 Pydantic 字段，处理嵌套对象。
    """
    prefix = "  " * indent

    for field_name, field_info in properties.items():
        is_req = "必填" if field_name in required else "可选"

        # 处理 $ref 引用 (Pydantic 用 $ref 引用嵌套模型)
        if "$ref" in field_info:
            # 从 ref 路径获取实际类型名
            ref_path = field_info["$ref"]
            type_name = ref_path.split("/")[-1]
            lines.append(f"{prefix}- {field_name}: {{...{type_name}对象...}} ({is_req})")
            continue

        field_type = field_info.get("type", "string")

        if field_type == "array":
            items = field_info.get("items", {})
            if "$ref" in items:
                ref_path = items["$ref"]
                type_name = ref_path.split("/")[-1]
                lines.append(f"{prefix}- {field_name}: [{type_name}对象数组] ({is_req})")
            else:
                item_type = items.get("type", "string")
                lines.append(f"{prefix}- {field_name}: [{item_type}数组] ({is_req})")

        elif field_type == "object":
            desc = field_info.get("description", "")
            lines.append(f"{prefix}- {field_name}: 对象 ({is_req}) - {desc}")
            # 递归描述子字段
            sub_props = field_info.get("properties", {})
            if sub_props:
                _describe_properties(sub_props, set(), lines, indent + 1)

        else:
            desc = field_info.get("description", "")
            lines.append(f"{prefix}- {field_name}: {field_type} ({is_req}) - {desc}")


def _build_example(schema_class: Type[BaseModel]) -> dict:
    """
    构建一个 JSON 示例，展示完整的嵌套结构。

    参数:
        schema_class: Pydantic 模型类
    返回:
        dict: 示例数据
    """
    example = {}
    schema = schema_class.model_json_schema()
    defs = schema.get("$defs", {})
    properties = schema.get("properties", {})

    for field_name, field_info in properties.items():
        example[field_name] = _make_example_value(field_info, defs)

    return example


def _make_example_value(field_info: dict, defs: dict) -> any:
    """递归构建单个字段的示例值。"""
    if "$ref" in field_info:
        ref_name = field_info["$ref"].split("/")[-1]
        if ref_name in defs:
            ref_schema = defs[ref_name]
            ref_props = ref_schema.get("properties", {})
            ref_example = {}
            for fn, fi in ref_props.items():
                ref_example[fn] = _make_example_value(fi, defs)
            return ref_example
        return {}

    field_type = field_info.get("type", "string")

    if field_type == "array":
        items = field_info.get("items", {})
        return [_make_example_value(items, defs)]

    elif field_type == "string":
        return "示例文本"

    elif field_type == "integer":
        return 0

    elif field_type == "number":
        return 0.0

    elif field_type == "boolean":
        return False

    return "未知类型"


def call_llm_structured(
    system_prompt: str,
    user_message: str,
    output_schema: Type[BaseModel],
) -> Any:
    """
    调用 LLM 并返回结构化响应 (自动选择最佳方式)。

    云端 (DeepSeek): 使用 with_structured_output(function_calling)
    本地 (qwen3): 使用 prompt-injection 方式
      1. 将 Pydantic Schema 转为文本说明，注入 system prompt
      2. 调用 LLM 获取 JSON 文本
      3. 用 Pydantic 验证并返回实例

    参数:
        system_prompt: 系统提示词
        user_message: 用户消息
        output_schema: Pydantic 模型类，用于约束输出格式
    返回:
        Pydantic Model 实例: 已验证的结构化数据
    """
    llm = _get_llm()

    if settings.llm.mode == "cloud":
        # 云端: 使用 LangChain 原生 function_calling
        structured_llm = llm.with_structured_output(
            output_schema,
            method="function_calling",
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]
        return structured_llm.invoke(messages)

    else:
        # 本地: prompt-injection 方式
        # qwen3-8b-mlx 不支持 tool_choice / json_mode，但能理解 prompt 中的格式要求

        # Step 1: 生成 JSON Schema 文本并注入 system prompt
        json_schema_text = _generate_json_schema(output_schema)
        enhanced_system_prompt = f"""{system_prompt}

{json_schema_text}

重要: 只输出上述 JSON 格式的内容，不要加 markdown 代码块标记 (```json```)，
不要加任何解释文字，确保输出的 JSON 可以被直接解析。"""

        # Step 2: 调用 LLM
        messages = [
            SystemMessage(content=enhanced_system_prompt),
            HumanMessage(content=user_message),
        ]

        response = llm.invoke(messages)
        raw_content = response.content.strip()

        # Step 3: 清理可能的 markdown 代码块标记
        # 有些模型即使说了不要加，也可能会加 ```json ... ```
        if raw_content.startswith("```"):
            # 找到第一个 ``` 并移除
            first_newline = raw_content.find("\n")
            if first_newline != -1:
                raw_content = raw_content[first_newline + 1:]
            # 移除结尾的 ```
            if raw_content.endswith("```"):
                raw_content = raw_content[:-3]
            raw_content = raw_content.strip()

        # Step 4: 解析 JSON 并验证
        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError as e:
            # JSON 解析失败，尝试截取第一个 { 到最后一个 } 之间的内容
            # 有时模型会在 JSON 前后加多余的空白或文字
            start = raw_content.find("{")
            end = raw_content.rfind("}")
            if start != -1 and end != -1 and start < end:
                try:
                    data = json.loads(raw_content[start:end + 1])
                except json.JSONDecodeError:
                    raise ValueError(f"LLM 返回的内容无法解析为 JSON:\n{raw_content[:500]}") from e
            else:
                raise ValueError(f"LLM 返回的内容无法解析为 JSON:\n{raw_content[:500]}") from e

        # Step 5: 用 Pydantic 验证数据
        return output_schema(**data)
