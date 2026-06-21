"""
app/services/rag_service.py
=============================
RAG (Retrieval-Augmented Generation) 证据检索服务。

串联整个 RAG Pipeline:
  文档文件 → 加载文本 → 切分Chunks → 生成Embedding → 存入Qdrant → 检索

这个服务被 LangGraph 的 evidence_retrieval_node 调用，
为 Match Agent 提供简历证据支撑。

核心流程:
  index_resume(file_path, candidate_id)
    → load_document → chunk_documents → generate_embeddings → store_chunks

  search_evidence(query_text, candidate_id)
    → generate_single_embedding → search_similar → 返回证据列表
"""

from typing import List, Dict, Any
from app.services.document_loader import load_document, chunk_documents
from app.services.embedding_service import generate_embeddings, generate_single_embedding
from app.services.vector_store import init_collection, store_chunks, search_similar


# 简历 chunks 在 Qdrant 中的集合名
# 所有简历的 chunks 都存在同一个集合中，通过 candidate_id 过滤
RESUME_COLLECTION = "resume_chunks"

# JD chunks 的集合名 (可选，后续 Phase 可能用到)
JD_COLLECTION = "jd_chunks"


def index_resume(
    file_path: str,
    candidate_id: str,
) -> List[str]:
    """
    索引一份简历: 加载 → 切分 → Embedding → 存入 Qdrant。

    这是 RAG 管线的入口。
    一份简历会被:
    1. 加载为 Document 对象 (按页)
    2. 切分为更小的 chunks (500字 + 50字重叠)
    3. 每个 chunk 生成一个 embedding 向量
    4. 向量 + 文本 + 元数据存入 Qdrant

    参数:
        file_path: 简历文件路径 (PDF/DOCX/TXT)
        candidate_id: 候选人的唯一ID (用于后续过滤检索)
    返回:
        List[str]: Qdrant point ID 列表 (每个 chunk 对应一个)
    """
    # Step 1: 加载文档
    # load_document 自动识别格式并返回 List[Document]
    documents = load_document(file_path)

    # Step 2: 切分为 chunks
    # chunk_documents 使用 RecursiveCharacterTextSplitter
    chunks = chunk_documents(documents)

    if not chunks:
        return []

    # Step 3: 提取文本列表
    chunk_texts = [chunk.page_content for chunk in chunks]

    # Step 4: 生成 embeddings
    # 批量生成比逐个快
    embeddings = generate_embeddings(chunk_texts)

    # Step 5: 构建元数据列表
    # 每个 chunk 都要带上 candidate_id，方便检索时过滤
    metadata_list = []
    for chunk in chunks:
        meta = {
            "candidate_id": candidate_id,
            "source": chunk.metadata.get("source", file_path),
            "page": chunk.metadata.get("page", 0),
        }
        metadata_list.append(meta)

    # Step 6: 确保集合存在
    init_collection(RESUME_COLLECTION)

    # Step 7: 存入 Qdrant (传入预生成的 ID, store_chunks 返回实际使用的 ID)
    import uuid
    point_ids = [str(uuid.uuid4()) for _ in chunks]
    actual_ids = store_chunks(
        chunks=chunk_texts,
        embeddings=embeddings,
        metadata_list=metadata_list,
        collection_name=RESUME_COLLECTION,
        point_ids=point_ids,  # 传入外部ID, store会用它们而非重新生成
    )

    return actual_ids  # 返回实际写入的ID (与传入的一致)


def search_evidence(
    query_text: str,
    candidate_id: str,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    从简历 chunks 中检索与查询相关的证据。

    用于 Match Agent 评分时查找支撑证据。
    例如: 查询"RAG 项目经验" → 找到简历中描述 RAG 项目的片段。

    参数:
        query_text: 查询文本 (例如: "Python FastAPI 后端开发经验")
        candidate_id: 只检索该候选人的 chunks (不会搜到其他候选人)
        top_k: 返回最相似的前 K 条
    返回:
        List[dict]: 搜索结果，每条包含 text, score, metadata
    """
    # Step 1: 将查询文本转为向量
    query_embedding = generate_single_embedding(query_text)

    # Step 2: 在 Qdrant 中搜索
    # filter_by={"candidate_id": candidate_id} 确保只搜该候选人的内容
    results = search_similar(
        query_embedding=query_embedding,
        collection_name=RESUME_COLLECTION,
        top_k=top_k,
        filter_by={"candidate_id": candidate_id},
    )

    return results


def search_evidence_for_match(
    jd_profile: Dict[str, Any],
    candidate_id: str,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    为 Match Agent 准备证据: 用 JD 中的关键要求构造查询。

    这个方法会自动从 JD profile 中提取关键信息作为查询词，
    然后检索候选人简历中相关的片段。

    参数:
        jd_profile: 结构化岗位信息
        candidate_id: 候选人ID
        top_k: 每条查询返回的 top K 结果
    返回:
        List[dict]: 汇总的证据列表 (去重后)
    """
    # 从 JD 中提取查询关键词
    queries = _build_queries_from_jd(jd_profile)

    # 对每条查询分别检索
    all_evidence = []
    seen_texts = set()  # 用于去重

    for query in queries:
        results = search_evidence(
            query_text=query,
            candidate_id=candidate_id,
            top_k=top_k,
        )

        # 去重: 相同的文本片段只保留一次
        for result in results:
            text_key = result["text"][:100]  # 用前100字符作为去重标识
            if text_key not in seen_texts:
                seen_texts.add(text_key)
                all_evidence.append(result)

    # 按相似度分数降序排列
    all_evidence.sort(key=lambda x: x.get("score", 0), reverse=True)

    # 返回 top_k 条
    return all_evidence[:top_k]


def index_resume_text(
    resume_text: str,
    candidate_id: str,
    source: str = "text_upload",
) -> List[str]:
    """
    索引简历文本 (不需要文件, 直接用文本)。

    用于 API 上传/粘贴简历文本后的索引:
    切分 → Embedding → Qdrant 存储。

    参数:
        resume_text: 简历纯文本
        candidate_id: 候选人ID
        source: 来源标记
    返回:
        List[str]: Qdrant point ID 列表
    """
    from langchain_core.documents import Document

    # 构造一个虚拟 Document (无文件路径)
    doc = Document(page_content=resume_text, metadata={"source": source})
    chunks = chunk_documents([doc])

    if not chunks:
        return []

    chunk_texts = [c.page_content for c in chunks]
    embeddings = generate_embeddings(chunk_texts)

    metadata_list = [
        {"candidate_id": candidate_id, "source": source, "page": 0}
        for _ in chunks
    ]

    init_collection(RESUME_COLLECTION)

    import uuid
    point_ids = [str(uuid.uuid4()) for _ in chunks]
    return store_chunks(
        chunks=chunk_texts,
        embeddings=embeddings,
        metadata_list=metadata_list,
        collection_name=RESUME_COLLECTION,
        point_ids=point_ids,
    )


def _build_queries_from_jd(jd_profile: Dict[str, Any]) -> List[str]:
    """
    从 JD profile 中构造检索查询词。

    提取岗位的关键要求，组合成多条查询语句，
    每条查询用来检索候选人简历中不同方面的证据。

    参数:
        jd_profile: 结构化岗位信息
    返回:
        List[str]: 查询语句列表
    """
    queries = []

    # 查询1: 用岗位名称 + 必备技能
    job_title = jd_profile.get("job_title", "")
    required_skills = jd_profile.get("required_skills", [])
    if required_skills:
        queries.append(f"{job_title} {' '.join(required_skills[:5])}")

    # 查询2: 用技术栈
    tech_reqs = jd_profile.get("technical_requirements", [])
    if tech_reqs:
        queries.append(" ".join(tech_reqs[:5]))

    # 查询3: 用加分技能
    preferred = jd_profile.get("preferred_skills", [])
    if preferred:
        queries.append(" ".join(preferred[:3]))

    # 如果全部为空，用岗位名称兜底
    if not queries:
        queries.append(job_title)

    return queries
