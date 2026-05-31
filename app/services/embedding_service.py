"""
app/services/embedding_service.py
==================================
Embedding 生成服务。

将文本转换为向量 (一系列浮点数)，用于语义搜索。
Embedding 向量是 RAG 检索的基础。

技术选型:
- OpenAI text-embedding-3-small 或
- 本地模型 (如 sentence-transformers) 以降低 API 成本
"""

from typing import List


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    为一组文本生成 embedding 向量。

    参数:
        texts: 要生成向量的文本列表
    返回:
        List[List[float]]: 每个文本对应的向量列表
                           向量维度取决于模型 (OpenAI 默认 1536)
    """
    # TODO: 实现 embedding 生成
    # 1. 选择合适的 embedding 模型
    # 2. 批量调用 API 或本地模型
    # 3. 返回向量列表
    pass


def generate_single_embedding(text: str) -> List[float]:
    """
    为单个文本生成 embedding 向量。

    参数:
        text: 要生成向量的文本
    返回:
        List[float]: 文本的向量表示
    """
    # TODO: 实现单文本 embedding
    pass
