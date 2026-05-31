"""
app/database/models.py
=======================
SQLAlchemy ORM 数据模型定义。

定义数据库中每个表的字段、类型和关系。
ORM (Object-Relational Mapping) 让你可以用 Python 对象操作数据库，
而不需要写原始 SQL 语句。
"""

# TODO: 实现数据库模型
# 使用 SQLAlchemy 定义以下表:

# 1. jobs 表: 岗位描述
#    - job_id (主键, UUID)
#    - title (岗位名称)
#    - company (公司)
#    - jd_text (原始文本)
#    - jd_profile_json (解析后的结构化 JSON)
#    - created_at (创建时间)

# 2. candidates 表: 候选人信息
#    - candidate_id (主键, UUID)
#    - name (姓名)
#    - email (邮箱)
#    - resume_text (原始简历文本)
#    - profile_json (解析后的结构化 JSON)
#    - created_at (创建时间)

# 3. resume_chunks 表: 简历文本块
#    - chunk_id (主键, UUID)
#    - candidate_id (外键 -> candidates)
#    - text (文本内容)
#    - embedding_id (向量数据库中的 ID)
#    - page_number (来源页码)

# 4. match_results 表: 匹配结果
#    - match_id (主键, UUID)
#    - job_id (外键 -> jobs)
#    - candidate_id (外键 -> candidates)
#    - total_score (总分)
#    - dimension_scores_json (各维度分数)
#    - evidence_json (证据)
#    - risk_json (风险点)
#    - created_at (创建时间)

# 5. interview_questions 表: 面试问题
#    - question_id (主键, UUID)
#    - job_id (外键 -> jobs)
#    - candidate_id (外键 -> candidates)
#    - question_type (问题类型)
#    - question (问题内容)
#    - purpose (提问目的)

# 6. interview_evaluations 表: 面试评价
#    - evaluation_id (主键, UUID)
#    - candidate_id (外键 -> candidates)
#    - job_id (外键 -> jobs)
#    - feedback_text (面试反馈)
#    - evaluation_json (结构化评价)
#    - final_recommendation (最终推荐)

# 7. email_drafts 表: 邮件草稿
#    - email_id (主键, UUID)
#    - candidate_id (外键 -> candidates)
#    - job_id (外键 -> jobs)
#    - email_type (类型)
#    - subject (标题)
#    - body (正文)
#    - status (草稿/已批准/已拒绝)
