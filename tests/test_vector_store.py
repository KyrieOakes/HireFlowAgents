"""
tests/test_vector_store.py
==========================
Qdrant 集合初始化与手动向量写入的回归测试。

项目自行生成 Embedding，因此初始化集合时不应该构造一个缺少 embedding 对象的
LangChain QdrantVectorStore。
"""

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# 测试从仓库根目录运行时可以直接导入 app 包。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.vector_store import init_collection, store_chunks


def test_init_existing_collection_returns_low_level_client():
    """集合已存在时直接返回 QdrantClient，不依赖 LangChain embedding 参数。"""
    client = MagicMock()
    client.get_collections.return_value = SimpleNamespace(
        collections=[SimpleNamespace(name="resume_chunks")]
    )

    with patch("app.services.vector_store._get_qdrant_client", return_value=client):
        returned = init_collection("resume_chunks", vector_size=2560)

    assert returned is client
    client.create_collection.assert_not_called()


def test_store_chunks_uses_manual_vectors_and_payload():
    """手动生成的向量和 candidate_id Payload 会原样写入底层 QdrantClient。"""
    client = MagicMock()

    with patch("app.services.vector_store.init_collection", return_value=client):
        ids = store_chunks(
            chunks=["Python LangGraph 项目"],
            embeddings=[[0.1, 0.2, 0.3]],
            metadata_list=[{"candidate_id": "C001", "source": "resume.pdf"}],
            collection_name="resume_chunks",
            point_ids=["point-1"],
        )

    assert ids == ["point-1"]
    points = client.upsert.call_args.kwargs["points"]
    assert points[0]["vector"] == [0.1, 0.2, 0.3]
    assert points[0]["payload"]["candidate_id"] == "C001"
