"""
app/services/matching_service.py
================================
匹配工作流启动前的公共准备服务。

当前只负责检查并自动重建候选人的 Qdrant 简历索引。
这段逻辑属于工作流前置服务，不应依附在某个 FastAPI 路由模块中。
"""

import asyncio
from typing import Awaitable, Callable, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import crud
from app.services.rag_service import ensure_resume_indexed


async def ensure_candidate_indexes(
    candidate_profiles: list[dict],
    candidate_records: dict[str, object],
    db: Session,
    progress_callback: Optional[Callable[..., Awaitable[None]]] = None,
) -> int:
    """
    匹配前检查候选人的 Qdrant 索引，并自动重建缺失项。

    输入:
        candidate_profiles: 本轮准备进入 Evidence Agent 的候选人画像。
        candidate_records: candidate_id 到数据库 Candidate 对象的映射。
        db: 用于同步派生 ResumeChunk 记录的数据库会话。
    输出:
        int: 本轮成功重建索引的候选人数。
    """
    from app.services.document_loader import chunk_documents
    from langchain_core.documents import Document

    rebuilt_count = 0
    failed_names: list[str] = []

    total = len(candidate_profiles)
    if progress_callback:
        await progress_callback(
            message=f"正在检查 {total} 名候选人的证据索引",
            completed=0,
            total=total,
        )

    for index, profile in enumerate(candidate_profiles, start=1):
        candidate_id = str(profile.get("candidate_id", ""))
        candidate_name = str(profile.get("name") or candidate_id or "未知候选人")
        candidate = candidate_records.get(candidate_id)
        if not candidate:
            failed_names.append(candidate_id or "未知候选人")
            if progress_callback:
                await progress_callback(
                    message=f"候选人记录缺失：{candidate_name}",
                    completed=index,
                    total=total,
                    candidate_id=candidate_id,
                    candidate_name=candidate_name,
                )
            continue

        try:
            # Qdrant 和 Embedding SDK 当前是同步接口，放入线程避免阻塞事件循环。
            point_ids = await asyncio.to_thread(
                ensure_resume_indexed,
                candidate.resume_text,
                candidate_id,
            )
            if point_ids is None:
                if progress_callback:
                    await progress_callback(
                        message=f"证据索引检查完成：{candidate_name}（{index}/{total}）",
                        completed=index,
                        total=total,
                        candidate_id=candidate_id,
                        candidate_name=candidate_name,
                    )
                continue

            # 自动重建成功后同步替换 PostgreSQL 中可再生的 chunk 映射。
            document = Document(
                page_content=candidate.resume_text,
                metadata={"source": "matching_auto_rebuild"},
            )
            chunks = chunk_documents([document])
            crud.save_resume_chunks(
                db,
                candidate_id,
                chunks,
                point_ids,
                replace_existing=True,
            )
            rebuilt_count += 1
            if progress_callback:
                await progress_callback(
                    message=f"已自动重建证据索引：{candidate_name}（{index}/{total}）",
                    completed=index,
                    total=total,
                    candidate_id=candidate_id,
                    candidate_name=candidate_name,
                )
        except Exception:
            # 不暴露底层服务地址或认证信息，只返回用户可以执行的排查建议。
            failed_names.append(str(profile.get("name") or candidate_id))
            if progress_callback:
                await progress_callback(
                    message=f"证据索引检查失败：{candidate_name}（{index}/{total}）",
                    completed=index,
                    total=total,
                    candidate_id=candidate_id,
                    candidate_name=candidate_name,
                )

    if failed_names:
        names = "、".join(failed_names[:5])
        suffix = "等" if len(failed_names) > 5 else ""
        raise HTTPException(
            status_code=503,
            detail=(
                f"以下候选人的简历证据索引不可用：{names}{suffix}。"
                "请确认 Qdrant 已启动，并在 LM Studio 中加载 Embedding 模型后重试匹配。"
            ),
        )

    if progress_callback:
        await progress_callback(
            status="completed",
            message=f"证据索引检查完成，共自动重建 {rebuilt_count} 人",
            completed=total,
            total=total,
        )

    return rebuilt_count
