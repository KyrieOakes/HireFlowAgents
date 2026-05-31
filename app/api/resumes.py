"""
app/api/resumes.py
===================
简历相关 API 路由。

处理简历上传、解析和候选人信息查询。
"""

from fastapi import APIRouter

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("/upload")
async def upload_resume():
    """
    上传简历。

    POST /resumes/upload

    支持上传 PDF 或 DOCX 格式的简历文件。
    可以一次上传多个文件。
    """
    # TODO: 实现简历上传
    # 1. 接收文件上传 (支持批量)
    # 2. 验证文件格式 (PDF/DOCX)
    # 3. 生成 candidate_id
    # 4. 保存文件到 data/resumes/
    # 5. 保存记录到数据库
    pass


@router.post("/candidates/{candidate_id}/parse")
async def parse_resume(candidate_id: str):
    """
    解析简历。

    POST /candidates/{candidate_id}/parse

    调用 Resume Agent 对已上传的简历进行结构化解析，
    提取候选人画像信息。
    """
    # TODO: 实现简历解析
    # 1. 从数据库读取简历文件路径
    # 2. 调用 document_loader 提取文本
    # 3. 调用 Resume Agent 解析
    # 4. 保存候选人画像到数据库
    pass


@router.get("/candidates/{candidate_id}")
async def get_candidate(candidate_id: str):
    """
    获取候选人详情。

    GET /candidates/{candidate_id}

    返回候选人的原始简历文本和解析后的结构化画像。
    """
    # TODO: 实现获取候选人详情
    # 1. 查询候选人基本信息
    # 2. 查询解析后的画像
    # 3. 返回完整候选人信息
    pass
