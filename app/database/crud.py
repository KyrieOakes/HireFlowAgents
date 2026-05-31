"""
app/database/crud.py
=====================
数据库 CRUD 操作。

CRUD = Create(创建) / Read(读取) / Update(更新) / Delete(删除)
封装所有对数据库的增删改查操作，供 API 路由和 Agent 调用。
"""

# TODO: 实现数据库 CRUD 函数

# 岗位相关:
# def create_job(db, job_data) -> Job
# def get_job(db, job_id) -> Job
# def update_job_profile(db, job_id, profile_json) -> Job

# 候选人相关:
# def create_candidate(db, candidate_data) -> Candidate
# def get_candidate(db, candidate_id) -> Candidate
# def update_candidate_profile(db, candidate_id, profile_json) -> Candidate
# def get_all_candidates(db) -> List[Candidate]

# 匹配结果相关:
# def save_match_result(db, match_data) -> MatchResult
# def get_match_results_by_job(db, job_id) -> List[MatchResult]
# def get_match_result(db, job_id, candidate_id) -> MatchResult

# 面试相关:
# def save_interview_questions(db, questions_data) -> List[InterviewQuestion]
# def get_interview_questions(db, candidate_id) -> List[InterviewQuestion]
# def save_evaluation(db, evaluation_data) -> InterviewEvaluation
# def get_evaluation(db, candidate_id) -> InterviewEvaluation

# 邮件相关:
# def save_email_draft(db, email_data) -> EmailDraft
# def get_email_draft(db, candidate_id) -> EmailDraft
# def update_email_status(db, email_id, status) -> EmailDraft
