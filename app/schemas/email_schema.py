"""
app/schemas/email_schema.py
===========================
HR 邮件 Agent 的结构化输出模型。

只让模型填写标题和正文；草稿状态与人工审批标记由后端固定生成，
避免模型越权改变审批流程。
"""

from pydantic import BaseModel, Field


class EmailContentOutput(BaseModel):
    """模型可生成的邮件内容字段。"""

    subject: str = Field(..., min_length=1, description="中文邮件标题")
    body: str = Field(..., min_length=1, description="中文邮件正文")
