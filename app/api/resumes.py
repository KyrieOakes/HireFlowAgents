"""
app/api/resumes.py
===================
简历相关 API。

POST /resumes/upload         → 上传简历文本，创建候选人记录
POST /resumes/{id}/parse     → 调用 Resume Agent 解析
GET  /resumes/{id}           → 获取候选人详情
GET  /resumes/               → 获取所有候选人列表
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.session import get_db
from app.database import crud
from app.agents.resume_agent import parse_resume

router = APIRouter(prefix="/resumes", tags=["resumes"])


# ---- 请求/响应模型 ----

class ResumeUploadRequest(BaseModel):
    """上传简历的请求体。"""
    # 简历纯文本 (必填，由前端或CLI从文件提取后传入)
    resume_text: str
    # 候选人姓名 (可选)
    name: str | None = None
    # 原始文件名 (可选)
    filename: str | None = None


class CandidateResponse(BaseModel):
    """候选人信息响应体。"""
    candidate_id: str
    name: str | None
    email: str | None
    filename: str | None
    profile: dict | None


# ---- API 端点 ----

@router.post("/upload")
async def upload_resume(
    request: ResumeUploadRequest,
    db: Session = Depends(get_db),
):
    """
    上传简历文本，创建候选人记录。

    请求体:
      {"resume_text": "简历全文...", "name": "可选", "filename": "简历.pdf"}

    返回: 创建的候选人基本信息
    """
    candidate = crud.create_candidate(
        db=db,
        resume_text=request.resume_text,
        name=request.name,
        filename=request.filename,
    )
    return {
        "candidate_id": candidate.candidate_id,
        "name": candidate.name,
        "message": "简历上传成功，请调用 /resumes/{id}/parse 进行解析",
    }


@router.post("/{candidate_id}/parse")
async def parse_resume_endpoint(
    candidate_id: str,
    db: Session = Depends(get_db),
):
    """
    调用 Resume Agent 解析简历。

    步骤:
    1. 从数据库读取简历文本
    2. 调用 Resume Agent 提取结构化画像
    3. 将解析结果保存回数据库

    返回: 解析后的结构化候选人画像
    """
    # Step 1: 查询候选人
    candidate = crud.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="候选人不存在")

    # Step 2: 调用 Resume Agent
    try:
        profile = await parse_resume(
            resume_text=candidate.resume_text,
            candidate_id=candidate_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"简历解析失败: {str(e)}")

    # Step 3: 保存解析结果
    crud.update_candidate_profile(db, candidate_id, profile)

    return {
        "candidate_id": candidate_id,
        "profile": profile,
    }


@router.get("/{candidate_id}")
async def get_candidate(
    candidate_id: str,
    db: Session = Depends(get_db),
):
    """
    获取候选人详情 (含解析结果)。

    返回: 候选人的原始文本 + 结构化画像
    """
    candidate = crud.get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="候选人不存在")

    return {
        "candidate_id": candidate.candidate_id,
        "name": candidate.name,
        "email": candidate.email,
        "resume_filename": candidate.resume_filename,
        "resume_text": candidate.resume_text,
        "profile": candidate.profile_json,
    }


@router.get("/")
async def list_candidates(db: Session = Depends(get_db)):
    """获取所有候选人列表。"""
    candidates = crud.get_all_candidates(db)
    return [
        {
            "candidate_id": c.candidate_id,
            "name": c.name,
            "email": c.email,
            "filename": c.resume_filename,
            "has_profile": c.profile_json is not None,
        }
        for c in candidates
    ]
