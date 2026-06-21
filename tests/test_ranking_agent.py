"""
tests/test_ranking_agent.py
===========================
Ranking Agent 单元测试 (mock LLM)。
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from unittest.mock import patch


def test_rank_candidates_sorting():
    """验证按总分降序排列。"""
    async def run():
        from app.agents.ranking_agent import rank_candidates
        with patch("app.agents.ranking_agent.call_llm") as mock:
            mock.return_value = "排名合理"
            result = await rank_candidates([
                {"candidate_id":"C2","total_score":70,"dimension_scores":{},"strengths":[],"risks":[],"recommendation":"Medium"},
                {"candidate_id":"C1","total_score":90,"dimension_scores":{},"strengths":[],"risks":[],"recommendation":"Strong"},
                {"candidate_id":"C3","total_score":55,"dimension_scores":{},"strengths":[],"risks":[],"recommendation":"Weak"},
            ])
        ranked = result["ranked_candidates"]
        assert ranked[0]["candidate_id"] == "C1"  # 最高分
        assert ranked[1]["candidate_id"] == "C2"
        assert ranked[2]["candidate_id"] == "C3"  # 最低分
        assert result["shortlist"]
        assert result["explanation"] == "排名合理"
    asyncio.run(run())


def test_recommendation_levels_in_ranking():
    """验证推荐等级在排序结果中正确分配。"""
    import asyncio
    async def run():
        from app.agents.ranking_agent import rank_candidates
        with patch("app.agents.ranking_agent.call_llm") as m:
            m.return_value = "ok"
            result = await rank_candidates([
                {"candidate_id":"C1","total_score":85,"dimension_scores":{},"strengths":[],"risks":[],"recommendation":""},
                {"candidate_id":"C2","total_score":70,"dimension_scores":{},"strengths":[],"risks":[],"recommendation":""},
                {"candidate_id":"C3","total_score":55,"dimension_scores":{},"strengths":[],"risks":[],"recommendation":""},
                {"candidate_id":"C4","total_score":40,"dimension_scores":{},"strengths":[],"risks":[],"recommendation":""},
            ])
        r = {c["candidate_id"]: c["recommendation"] for c in result["ranked_candidates"]}
        assert r["C1"] == "Strong Match"
        assert r["C2"] == "Medium Match"
        assert r["C3"] == "Weak Match"
        assert r["C4"] == "Not Recommended"
    asyncio.run(run())


def test_ranking_summary():
    """验证汇总统计。"""
    async def run():
        from app.agents.ranking_agent import rank_candidates
        with patch("app.agents.ranking_agent.call_llm") as mock:
            mock.return_value = "统计正确"
            result = await rank_candidates([
                {"candidate_id":"C1","total_score":85,"dimension_scores":{},"strengths":[],"risks":[],"recommendation":"Strong"},
                {"candidate_id":"C2","total_score":70,"dimension_scores":{},"strengths":[],"risks":[],"recommendation":"Medium"},
                {"candidate_id":"C3","total_score":40,"dimension_scores":{},"strengths":[],"risks":[],"recommendation":"Weak"},
            ])
        s = result["summary"]
        assert s["total_candidates"] == 3
        assert s["strong_match"] == 1
        assert s["medium_match"] == 1
        assert s["not_recommended"] == 1
    asyncio.run(run())
