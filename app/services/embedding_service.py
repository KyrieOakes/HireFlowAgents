"""
app/services/embedding_service.py
==================================
Embedding 生成服务 (Local + Cloud 双模式)。

将文本转换为向量，用于语义搜索。
使用 OpenAI SDK 直接调用 (兼容 LM Studio 和 DeepSeek)。

注意: 不使用 LangChain 的 OpenAIEmbeddings 封装，
因为 LM Studio 对其请求格式兼容性不好。
直接使用 OpenAI SDK 更稳定。
"""

from typing import List
from openai import OpenAI
from app.utils.config import settings


def _get_client() -> OpenAI:
    """
    根据配置创建 OpenAI 兼容客户端。

    返回:
        OpenAI: 配置好的客户端实例
    """
    emb_config = settings.embedding

    if emb_config.mode == "local":
        base_url = emb_config.local_base_url
        api_key = emb_config.local_api_key
    else:
        base_url = emb_config.cloud_base_url
        api_key = emb_config.cloud_api_key

    return OpenAI(
        base_url=base_url,
        api_key=api_key,
    )


def _get_model_name() -> str:
    """获取当前模式下的 embedding 模型名称。"""
    emb_config = settings.embedding
    if emb_config.mode == "local":
        return emb_config.local_model
    return emb_config.cloud_model


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    为一组文本批量生成 embedding 向量。

    参数:
        texts: 要向量化的文本列表
    返回:
        List[List[float]]: 每个文本对应的向量，维度取决于模型 (qwen3 = 2560)
    """
    client = _get_client()
    model = _get_model_name()

    # 直接调用 OpenAI 兼容 API
    response = client.embeddings.create(
        model=model,
        input=texts,
    )

    # 按输入顺序提取向量
    # data 数组已经按 input 顺序排列
    embeddings = [item.embedding for item in response.data]

    return embeddings


def generate_single_embedding(text: str) -> List[float]:
    """
    为单个文本生成 embedding 向量。

    参数:
        text: 要向量化的单条文本
    返回:
        List[float]: 文本的向量表示
    """
    client = _get_client()
    model = _get_model_name()

    response = client.embeddings.create(
        model=model,
        input=text,
    )

    # 单条输入只返回一个结果
    return response.data[0].embedding
