"""
app/api/matching.py
====================
候选人匹配与排序相关 API 路由。

处理候选人匹配评分、排名查询和匹配结果获取。
"""

from fastapi import APIRouter

router = APIRouter(tags=["matching"])


@router.post("/jobs/{job_id}/match")
async def run_matching(job_id: str):
    """
    执行候选人匹配。

    POST /jobs/{job_id}/match

    对指定岗位的所有候选人进行匹配评分。
    调用 Match Agent 和 Ranking Agent。
    """
    # TODO: 实现匹配流程
    # 1. 获取 job_id 对应的 jd_profile
    # 2. 获取该岗位下所有候选人的 profile
    # 3. 执行 RAG 证据检索
    # 4. 调用 Match Agent 对每个候选人评分
    # 5. 调用 Ranking Agent 排序
    # 6. 保存结果到数据库
    pass


@router.get("/jobs/{job_id}/ranking")
async def get_ranking(job_id: str):
    """
    获取候选人排名。

    GET /jobs/{job_id}/ranking

    返回指定岗位下所有候选人的排序结果。
    """
    # TODO: 实现获取排名
    # 1. 查询 match_results 表
    # 2. 按 total_score 降序排列
    # 3. 返回排序后的候选人列表
    pass


@router.get("/jobs/{job_id}/candidates/{candidate_id}/match-result")
async def get_match_result(job_id: str, candidate_id: str):
    """
    获取单个候选人的详细匹配结果。

    GET /jobs/{job_id}/candidates/{candidate_id}/match-result

    返回某个候选人在某个岗位下的完整评分详情，包括证据。
    """
    # TODO: 实现获取单个匹配结果
    # 1. 查询 match_results 表
    # 2. 返回维度分数 + 证据 + 风险点
    pass
