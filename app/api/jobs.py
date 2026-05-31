"""
app/api/jobs.py
================
岗位描述相关 API。

POST /jobs/upload  → 上传岗位描述文本，创建岗位记录
POST /jobs/{job_id}/parse → 调用 JD Agent 解析
GET  /jobs/{job_id} → 获取岗位详情和解析结果
GET  /jobs/ → 获取所有岗位列表
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.session import get_db
from app.database import crud
from app.agents.jd_agent import analyze_jd

router = APIRouter(prefix="/jobs", tags=["jobs"])


# ---- 请求/响应模型 ----

class JobUploadRequest(BaseModel):
    """上传岗位描述的请求体。"""
    # 岗位描述全文 (必填)
    jd_text: str
    # 岗位名称 (可选，解析后可更新)
    title: str | None = None


class JobResponse(BaseModel):
    """岗位信息响应体。"""
    job_id: str
    title: str | None
    jd_text: str
    jd_profile: dict | None
    rubric: dict | None


# ---- API 端点 ----

@router.post("/upload")
async def upload_job(request: JobUploadRequest, db: Session = Depends(get_db)):
    """
    上传岗位描述文本，创建岗位记录。

    请求体:
      {"jd_text": "岗位描述全文...", "title": "可选标题"}

    返回: 创建的岗位基本信息
    """
    # 创建岗位记录
    job = crud.create_job(
        db=db,
        jd_text=request.jd_text,
        title=request.title,
    )
    return {
        "job_id": job.job_id,
        "title": job.title,
        "message": "岗位创建成功，请调用 /jobs/{job_id}/parse 进行解析",
    }


@router.post("/{job_id}/parse")
async def parse_job(job_id: str, db: Session = Depends(get_db)):
    """
    调用 JD Agent 解析岗位描述。

    步骤:
    1. 从数据库读取原始 JD 文本
    2. 调用 JD Agent 提取结构化信息 + 生成 Rubric
    3. 将解析结果保存回数据库

    返回: 解析后的结构化岗位信息
    """
    # Step 1: 查询岗位
    job = crud.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在")

    # Step 2: 调用 JD Agent
    try:
        jd_profile = await analyze_jd(job.jd_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JD 解析失败: {str(e)}")

    # Step 3: 保存解析结果
    rubric = jd_profile.pop("rubric", None)
    crud.update_job_profile(db, job_id, jd_profile, rubric)

    # 把 rubric 放回去一起返回
    jd_profile["rubric"] = rubric

    return {
        "job_id": job_id,
        "jd_profile": jd_profile,
    }


@router.get("/{job_id}")
async def get_job(job_id: str, db: Session = Depends(get_db)):
    """
    获取岗位详情 (含解析结果)。

    返回: 岗位的原始文本 + 结构化解析结果 + Rubric
    """
    job = crud.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在")

    return {
        "job_id": job.job_id,
        "title": job.title,
        "jd_text": job.jd_text,
        "jd_profile": job.jd_profile_json,
        "rubric": job.rubric_json,
    }


@router.get("/")
async def list_jobs(db: Session = Depends(get_db)):
    """获取所有岗位列表。"""
    jobs = crud.get_all_jobs(db)
    return [
        {
            "job_id": j.job_id,
            "title": j.title,
            "has_profile": j.jd_profile_json is not None,
        }
        for j in jobs
    ]
