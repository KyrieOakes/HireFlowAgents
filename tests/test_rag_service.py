"""
tests/test_rag_service.py
=========================
RAG 索引健康检查与自动重建测试。

这些测试不连接真实 LM Studio 或 Qdrant，而是用 mock 锁住两个关键语义：
缺失索引不能伪装成“业务证据不足”，匹配前可以使用简历原文自动重建索引。
"""

import os
import sys
from unittest.mock import patch

import pytest

# 测试从仓库根目录运行时可以直接导入 app 包。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.rag_service import (
    ResumeIndexMissingError,
    ensure_resume_indexed,
    search_evidence,
)


def test_empty_search_with_missing_index_is_system_error():
    """候选人在 Qdrant 中没有任何向量时必须报索引错误，而不是证据不足。"""
    with patch(
        "app.services.rag_service.generate_single_embedding",
        return_value=[0.1, 0.2],
    ), patch(
        "app.services.rag_service.search_similar",
        return_value=[],
    ), patch(
        "app.services.rag_service.resume_index_exists",
        return_value=False,
    ):
        with pytest.raises(ResumeIndexMissingError):
            search_evidence("Python Agent", "C001", top_k=3)


def test_ensure_resume_indexed_rebuilds_missing_candidate():
    """匹配前发现索引缺失时，会用数据库中的简历原文自动重建。"""
    with patch(
        "app.services.rag_service.resume_index_exists",
        return_value=False,
    ), patch(
        "app.services.rag_service.index_resume_text",
        return_value=["point-1", "point-2"],
    ) as rebuild:
        point_ids = ensure_resume_indexed("Python LangGraph 项目经验", "C001")

    assert point_ids == ["point-1", "point-2"]
    rebuild.assert_called_once_with(
        resume_text="Python LangGraph 项目经验",
        candidate_id="C001",
        source="matching_auto_rebuild",
    )


def test_ensure_resume_indexed_skips_existing_candidate():
    """已有索引时不重复生成 Embedding，避免每次匹配都增加延迟和重复向量。"""
    with patch(
        "app.services.rag_service.resume_index_exists",
        return_value=True,
    ), patch("app.services.rag_service.index_resume_text") as rebuild:
        point_ids = ensure_resume_indexed("已有简历", "C001")

    assert point_ids is None
    rebuild.assert_not_called()
