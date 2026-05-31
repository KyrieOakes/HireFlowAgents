"""
app/api/evaluation.py
======================
评估和邮件相关 API 路由。

处理系统评估报告、邮件草稿生成和邮件审核。
"""

from fastapi import APIRouter

router = APIRouter(tags=["evaluation"])


# ---- 评估报告 API ----

@router.get("/evaluation/report")
async def get_evaluation_report():
    """
    获取系统评估报告。

    GET /evaluation/report

    返回简历解析准确率、排序质量、RAG 证据质量等评估指标。
    """
    # TODO: 实现评估报告
    # 1. 运行各评估脚本
    # 2. 汇总指标
    # 3. 返回 JSON 格式报告
    pass


@router.get("/evaluation/parsing")
async def get_parsing_eval():
    """
    获取简历解析评估结果。

    GET /evaluation/parsing
    """
    pass


@router.get("/evaluation/ranking")
async def get_ranking_eval():
    """
    获取排序评估结果。

    GET /evaluation/ranking
    """
    pass


@router.get("/evaluation/workflow")
async def get_workflow_eval():
    """
    获取工作流可靠性评估结果。

    GET /evaluation/workflow
    """
    pass


# ---- 邮件相关 API ----

@router.post("/candidates/{candidate_id}/email-draft")
async def generate_email_draft(candidate_id: str):
    """
    生成 HR 邮件草稿。

    POST /candidates/{candidate_id}/email-draft

    根据候选人状态生成对应类型的邮件草稿。
    系统只生成草稿，不自动发送。
    """
    # TODO: 实现邮件草稿生成
    # 1. 确定邮件类型 (根据候选人状态)
    # 2. 调用 Email Agent 生成
    # 3. 保存为草稿状态
    pass


@router.get("/candidates/{candidate_id}/email-draft")
async def get_email_draft(candidate_id: str):
    """
    获取候选人的邮件草稿。

    GET /candidates/{candidate_id}/email-draft
    """
    pass


@router.post("/email-drafts/{email_id}/approve")
async def approve_email(email_id: str):
    """
    批准邮件草稿。

    POST /email-drafts/{email_id}/approve

    人工审核通过后，批准邮件以便发送。
    注意: 批准 ≠ 发送，还需要额外的发送步骤。
    """
    # TODO: 实现邮件审核
    # 1. 更新邮件状态为 "approved"
    # 2. 记录审核人和审核时间
    pass
