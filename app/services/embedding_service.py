"""
app/services/embedding_service.py
==================================
Embedding 生成服务 (Local + Cloud 双模式)。

将文本转换为向量 (一串浮点数)，用于语义搜索。
向量之间的"距离"代表文本之间的"语义相似度"。

支持两种模式:
- "local": 使用 LM Studio 本地 embedding 模型，免费
- "cloud": 使用 DeepSeek Embedding API，生产级

两者都是 OpenAI 兼容接口，使用同一个 OpenAIEmbeddings 类。
"""

from typing import List
from langchain_openai import OpenAIEmbeddings
from app.utils.config import settings


def _get_embeddings_client() -> OpenAIEmbeddings:
    """
    根据配置创建 Embedding 客户端。

    OpenAIEmbeddings 是 LangChain 封装的 embedding 客户端。
    和 LLM 一样，支持任何 OpenAI 兼容的 embedding API。

    返回:
        OpenAIEmbeddings: 配置好的 embedding 客户端
    """
    emb_config = settings.embedding

    if emb_config.mode == "local":
        base_url = emb_config.local_base_url
        api_key = emb_config.local_api_key
        model = emb_config.local_model
    else:
        base_url = emb_config.cloud_base_url
        api_key = emb_config.cloud_api_key
        model = emb_config.cloud_model

    return OpenAIEmbeddings(
        base_url=base_url,
        api_key=api_key,
        model=model,
    )


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    为一组文本批量生成 embedding 向量。

    批量调用比逐个调用快很多 (减少 API 往返次数)。

    参数:
        texts: 要向量化的文本列表，例如 ["Python 3年经验", "熟悉 Docker"]
    返回:
        List[List[float]]: 每个文本对应的向量
                           例如: [[0.1, 0.3, ...], [0.2, 0.5, ...]]
                           向量维度取决于模型 (DeepSeek 默认 1536)
    """
    # 获取 embedding 客户端
    client = _get_embeddings_client()

    # embed_documents() 是 LangChain 的批量向量化方法
    # 内部会处理 batch、重试、限流等逻辑
    embeddings = client.embed_documents(texts)

    return embeddings


def generate_single_embedding(text: str) -> List[float]:
    """
    为单个文本生成 embedding 向量。

    适用于: 用户输入的查询 (如搜索时)。

    参数:
        text: 要向量化的单条文本
    返回:
        List[float]: 文本的向量表示
    """
    client = _get_embeddings_client()

    # embed_query() 专门为单条查询文本设计
    # 和 embed_documents() 的区别: embed_query() 可能对查询文本做特殊处理
    embedding = client.embed_query(text)

    return embedding
