"""
app/api/interview.py
=====================
面试相关 API 路由。

处理面试问题生成、面试评价提交和查询。
"""

from fastapi import APIRouter

router = APIRouter(tags=["interview"])


@router.post("/candidates/{candidate_id}/questions")
async def generate_questions(candidate_id: str):
    """
    为指定候选人生成面试问题。

    POST /candidates/{candidate_id}/questions

    根据候选人的简历、匹配结果和风险点，生成定制化面试问题。
    """
    # TODO: 实现面试问题生成
    # 1. 获取候选人 profile 和 match result
    # 2. 获取岗位 jd_profile
    # 3. 调用 Interview Agent 生成问题
    # 4. 保存到 interview_questions 表
    pass


@router.post("/candidates/{candidate_id}/evaluate")
async def evaluate_candidate(candidate_id: str):
    """
    提交面试评价。

    POST /candidates/{candidate_id}/evaluate

    面试结束后，面试官输入反馈，系统自动生成评价。
    """
    # TODO: 实现面试评价
    # 1. 接收面试记录或面试官反馈文本
    # 2. 获取候选人 profile 和 match result
    # 3. 调用 Evaluation Agent 生成评价
    # 4. 保存到 interview_evaluations 表
    pass


@router.get("/candidates/{candidate_id}/evaluation")
async def get_evaluation(candidate_id: str):
    """
    获取候选人面试评价。

    GET /candidates/{candidate_id}/evaluation
    """
    # TODO: 实现获取面试评价
    pass
