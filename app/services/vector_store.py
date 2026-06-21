"""
app/services/vector_store.py
==============================
向量数据库服务 (Qdrant)。

使用 Qdrant 存储和检索文本的 embedding 向量。
Qdrant 是 Rust 编写的高性能向量数据库，支持:
- 语义相似度搜索
- Payload filtering (按 metadata 字段过滤)
- 多种距离算法 (Cosine, Euclidean, Dot Product)

部署方式:
- Docker Compose 独立容器 (推荐)
- 本地直接运行

依赖: pip install qdrant-client langchain-qdrant
"""

from typing import List, Dict, Any, Optional
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from app.utils.config import settings


def _get_qdrant_client() -> QdrantClient:
    """
    创建 Qdrant 客户端连接。

    QdrantClient 是底层连接对象，用于管理 Collection (建表、删表等)。
    上层检索使用 QdrantVectorStore (LangChain 封装)。

    返回:
        QdrantClient: Qdrant 底层客户端
    """
    qdrant_config = settings.qdrant

    # 创建客户端
    # url: Qdrant 服务地址 (Docker 中默认 http://localhost:6333)
    # api_key: 生产环境用，本地开发留空
    return QdrantClient(
        url=qdrant_config.url,
        api_key=qdrant_config.api_key if qdrant_config.api_key else None,
    )


def init_collection(
    collection_name: str,
    vector_size: int = 2560,  # qwen3-embedding-4b 维度 = 2560
) -> QdrantVectorStore:
    """
    初始化 Qdrant 集合 (Collection)。

    集合 = 数据库中的"表"，用于存储一组相关的向量。
    例如: 为简历 chunks 创建一个 collection，为 JD chunks 创建另一个。

    参数:
        collection_name: 集合名称，如 "resumes" 或 "job_descriptions"
        vector_size: 向量维度 (text-embedding-qwen3-embedding-4b = 2560)
    返回:
        QdrantVectorStore: LangChain 封装的上层检索接口
    """
    client = _get_qdrant_client()

    # 检查集合是否已存在
    # 如果已存在就跳过创建，否则 Qdrant 会报错
    collections = client.get_collections()
    collection_names = [c.name for c in collections.collections]

    if collection_name not in collection_names:
        # 创建新集合
        # Distance.COSINE: 使用余弦相似度衡量向量距离
        # 余弦相似度关注"方向"而非"长度"，适合文本语义比较
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )

    # 用 LangChain 封装返回，方便后续操作
    # QdrantVectorStore 提供了 add_documents, similarity_search 等上层方法
    embedding_client = None  # 这里不传 embedding，用手动生成的向量
    vector_store = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
    )

    return vector_store


def store_chunks(
    chunks: List[str],
    embeddings: List[List[float]],
    metadata_list: List[Dict[str, Any]],
    collection_name: str,
    point_ids: List[str] | None = None,  # 可选: 外部生成的ID, 用于关联DB
):
    """
    将文本 chunks 和它们的 embedding 存入 Qdrant。

    每个 chunk 包含三部分:
    - 文本内容 (page_content): 简历或 JD 的原文片段
    - 向量 (embedding): 文本的数值表示，用于相似度搜索
    - 元数据 (metadata): 如 candidate_id, page_number, source 等

    参数:
        chunks: 原始文本块列表
        embeddings: 每个文本块对应的向量
        metadata_list: 每个文本块的元数据
        collection_name: 存入哪个集合
        point_ids: 可选, 外部生成的point ID列表 (用于与DB记录关联)
    返回:
        List[str]: 实际使用的 point ID 列表
    """
    from langchain_core.documents import Document

    # 确保集合存在
    vector_store = init_collection(collection_name)

    # 构造 Document 对象列表
    # LangChain 的 Document 是一个数据类，包含 page_content 和 metadata
    documents = []
    for text, embedding, meta in zip(chunks, embeddings, metadata_list):
        doc = Document(page_content=text, metadata=meta)
        documents.append(doc)

    # 批量存入 Qdrant
    # add_documents() 内部会:
    # 1. 用 embedding 参数传入的向量 (或自动生成) 索引每条文档
    # 2. 存储文本和元数据
    # 注意: 我们手动传入了 embeddings，所以 Qdrant 不会再调用 embedding API
    # 使用 add_documents 的方式，需要传入 ids 并手动调用 client.upsert
    # 简化方案: 直接用底层 client 的 upsert
    client = _get_qdrant_client()

    # 生成唯一 ID 列表 (如果外部传入了 point_ids 则使用外部ID)
    import uuid
    ids = point_ids if point_ids else [str(uuid.uuid4()) for _ in documents]

    # 手动 upsert: 同时插入向量 + payload
    client.upsert(
        collection_name=collection_name,
        points=[
            {
                "id": ids[i],
                "vector": embeddings[i],
                "payload": {
                    "page_content": documents[i].page_content,
                    **documents[i].metadata,
                },
            }
            for i in range(len(documents))
        ],
    )

    return ids  # 返回实际使用的 point ID 列表


def search_similar(
    query_embedding: List[float],
    collection_name: str,
    top_k: int = 5,
    filter_by: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    在 Qdrant 中搜索与查询向量最相似的文本块。

    这是 RAG 证据检索的核心方法:
    Match Agent 需要证据时，用岗位相关关键词的 embedding 搜索简历 chunks。

    参数:
        query_embedding: 查询文本的 embedding 向量
        collection_name: 在哪个集合中搜索
        top_k: 返回最相似的前 K 个结果
        filter_by: Payload 过滤条件，如 {"candidate_id": "C001"}
                   这样只会在候选人 C001 的 chunks 中搜索，不会搜到其他人
    返回:
        List[Dict]: 每个结果包含:
            - text: 匹配到的原文片段
            - score: 相似度分数 (越高越相关)
            - metadata: 该 chunk 的元数据
    """
    client = _get_qdrant_client()

    # 构造搜索请求
    # query_points: 传入向量 + 搜索参数
    search_result = client.query_points(
        collection_name=collection_name,
        query=query_embedding,
        limit=top_k,
        # query_filter: 按 metadata 字段过滤
        # 例如: 只检索候选人 C001 的简历 chunks
        query_filter=(
            {"must": [{"key": k, "match": {"value": v}} for k, v in filter_by.items()]}
            if filter_by
            else None
        ),
    )

    # 整理返回结果
    results = []
    for point in search_result.points:
        results.append({
            "text": point.payload.get("page_content", ""),
            "score": point.score,
            "metadata": {k: v for k, v in point.payload.items() if k != "page_content"},
        })

    return results
