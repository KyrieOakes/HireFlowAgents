"""
app/api/jobs.py
================
岗位描述相关 API 路由。

使用 FastAPI 的 APIRouter 将相关的路由组织在一起，
每个路由函数处理一个 HTTP 请求。
"""

from fastapi import APIRouter

# 创建路由器实例，所有岗位相关的 API 端点都在这里定义
# prefix="/jobs" 表示这个 router 中所有路径都会自动在前面加上 /jobs
# tags=["jobs"] 会在自动生成的 API 文档中创建一个 "jobs" 分组
router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/upload")
async def upload_job():
    """
    上传岗位描述。

    POST /jobs/upload

    用户上传 PDF 或粘贴文本形式的岗位描述。
    系统保存原始文件，然后调用 JD Agent 进行解析。
    """
    # TODO: 实现岗位描述上传
    # 1. 接收文件上传或文本输入
    # 2. 生成 job_id
    # 3. 保存到数据库和文件系统
    # 4. 触发异步解析任务
    pass


@router.post("/{job_id}/parse")
async def parse_job(job_id: str):
    """
    解析岗位描述。

    POST /jobs/{job_id}/parse

    调用 JD Agent 对已上传的岗位描述进行结构化解析。
    {job_id} 是路径参数，会传入函数参数。
    """
    # TODO: 实现岗位描述解析
    # 1. 从数据库读取 job_id 对应的原始文本
    # 2. 调用 JD Agent 进行解析
    # 3. 将结构化结果保存到数据库
    # 4. 返回解析后的 jd_profile
    pass


@router.get("/{job_id}")
async def get_job(job_id: str):
    """
    获取岗位详情。

    GET /jobs/{job_id}

    返回指定岗位的原始描述和解析后的结构化信息。
    """
    # TODO: 实现获取岗位详情
    # 1. 从数据库查询 job_id 对应的记录
    # 2. 返回原始 JD 文本 + 解析后的 jd_profile
    pass
