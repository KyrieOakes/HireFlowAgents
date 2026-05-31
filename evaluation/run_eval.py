#!/usr/bin/env python3
"""
evaluation/run_eval.py
=======================
自动化评估脚本。

运行完整 Pipeline 并输出多维度评估指标。
可以作为脚本独立运行，也可以被 Notebook 导入。
每次执行后会:
1. 在 reports/ 生成一份带时间戳的 .md 报告
2. 在同一目录生成一份 .json 结构化指标 (方便程序化对比)

指标:
- Precision@K: 系统 Top K 中真正合适的候选人比例
- NDCG@K: 系统排序与理想排序的归一化折扣累积增益
- 延迟分布: 各步骤耗时
- 分数分布: 各等级候选人数量
- 一致性: (多次运行对比)

用法:
  python evaluation/run_eval.py
"""

import sys
import os
import time
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Tuple

# 确保项目根目录在 Python 路径中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


# ================================================================
# 测试数据
# ================================================================

TEST_JD = """
岗位名称: Python 后端开发工程师
必备技能: Python, FastAPI, PostgreSQL, Docker, Git
加分技能: LangChain, RAG, Redis
岗位职责: 开发后端API, 数据库设计, 编写单元测试
学历要求: 计算机相关专业本科及以上
经验要求: 0-3年
"""

TEST_RESUMES: Dict[str, str] = {
    "E001": (
        "姓名: 张工\n"
        "技能: Python, FastAPI, PostgreSQL, Docker, Git, Redis\n"
        "项目: 电商API - FastAPI+PostgreSQL+Docker\n"
        "教育: 2020-2024 北大 CS学士\n"
        "经历: 2023某公司Python实习生"
    ),
    "E002": (
        "姓名: 李工\n"
        "技能: Python, Django, MySQL, Docker, Git\n"
        "项目: 博客系统 - Django+MySQL\n"
        "教育: 2019-2023 浙大 SE学士\n"
        "经历: 2022某公司Django实习生"
    ),
    "E003": (
        "姓名: 王工\n"
        "技能: Python, FastAPI, PostgreSQL, LangChain, RAG, Docker, Git, Redis\n"
        "项目: RAG问答系统 - FastAPI+LangChain+Qdrant\n"
        "教育: 2021-2023 清华 AI硕士\n"
        "经历: 2023某AI公司后端实习生"
    ),
}


# ================================================================
# 代理 Ground Truth 构建 (基于关键词匹配)
# ================================================================

def _build_proxy_relevance(
    jd_skills: List[str],
    resumes: Dict[str, str],
) -> Dict[str, float]:
    """
    构建代理"正确答案"。

    由于没有人工标注数据，使用 JD 必备技能在简历中的命中率
    作为候选人相关性分数 (proxy ground truth)。

    这不是真正的 ground truth (忽略了项目经验、学历等维度)，
    但可以作为评估框架的占位指标，展示 Precision@K / NDCG 的计算方式。

    参数:
        jd_skills: JD 的必备技能列表
        resumes: {candidate_id: resume_text}
    返回:
        {candidate_id: relevance_score (0.0-1.0)}
    """
    relevance = {}
    for cid, text in resumes.items():
        text_lower = text.lower()
        hits = sum(1 for skill in jd_skills if skill.lower() in text_lower)
        relevance[cid] = hits / max(len(jd_skills), 1)
    return relevance


# ================================================================
# 评估指标计算
# ================================================================

def precision_at_k(
    ranked_ids: List[str],
    relevance: Dict[str, float],
    k: int,
    threshold: float = 0.5,
) -> float:
    """
    Precision@K: 系统 Top K 中真正相关的候选人比例。

    参数:
        ranked_ids: 系统排序的候选人ID列表 (从高到低)
        relevance: 每个候选人的真实相关度
        k: 取前 K 个
        threshold: 相关度阈值, >= threshold 视为"相关"
    返回:
        float: 0.0 - 1.0
    """
    top_k = ranked_ids[:k]
    if not top_k:
        return 0.0
    relevant = sum(1 for cid in top_k if relevance.get(cid, 0) >= threshold)
    return relevant / k


def ndcg_at_k(
    ranked_ids: List[str],
    relevance: Dict[str, float],
    k: int,
) -> float:
    """
    NDCG@K: 归一化折扣累积增益。

    衡量系统排序与理想排序的接近程度。
    DCG = sum(relevance_i / log2(i+2)) for i in range(k)
    IDCG = 理想排序下的 DCG (按 relevance 降序排列)
    NDCG = DCG / IDCG

    参数:
        ranked_ids: 系统排序 (从高到低)
        relevance: 每个候选人的真实相关度
        k: 取前 K 个
    返回:
        float: 0.0 - 1.0 (1.0 = 完美排序)
    """
    import math

    if not ranked_ids or not relevance:
        return 0.0

    # DCG: 系统排序的折扣累积增益
    dcg = 0.0
    for i, cid in enumerate(ranked_ids[:k]):
        rel = relevance.get(cid, 0.0)
        dcg += rel / math.log2(i + 2)  # i+2 因为 i 从 0 开始

    # IDCG: 理想排序 (按相关度降序)
    ideal_order = sorted(relevance.keys(), key=lambda x: relevance.get(x, 0), reverse=True)
    idcg = 0.0
    for i, cid in enumerate(ideal_order[:k]):
        rel = relevance.get(cid, 0.0)
        idcg += rel / math.log2(i + 2)

    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def spearman_rank_correlation(
    ranked_ids: List[str],
    relevance: Dict[str, float],
) -> float:
    """
    Spearman 秩相关系数: 系统排序和理想排序的关联程度。

    取值 -1 到 1, 1 表示完全一致。

    参数:
        ranked_ids: 系统排序
        relevance: 相关度
    返回:
        float: -1.0 到 1.0
    """
    # 理想排序
    ideal = sorted(relevance.keys(), key=lambda x: relevance.get(x, 0), reverse=True)

    # 给每个候选人分配秩次
    system_rank = {cid: i for i, cid in enumerate(ranked_ids)}
    ideal_rank = {cid: i for i, cid in enumerate(ideal)}

    n = len(ranked_ids)
    if n < 2:
        return 0.0

    # 计算秩差平方和
    d_squared_sum = 0
    for cid in ranked_ids:
        d = system_rank.get(cid, n) - ideal_rank.get(cid, n)
        d_squared_sum += d * d

    # Spearman 公式
    rho = 1 - (6 * d_squared_sum) / (n * (n * n - 1))
    return rho


# ================================================================
# 主评估流程
# ================================================================

async def run_evaluation() -> Dict[str, Any]:
    """
    运行完整评估流程。

    返回:
        dict: {
            "timestamp": str,
            "pipeline": {"steps": [...], "total_time": float},
            "ranking": {...},
            "metrics": {"precision_at_1": float, "precision_at_3": float, ...},
            "scores": [...],
        }
    """
    from app.agents.jd_agent import analyze_jd
    from app.agents.resume_agent import batch_parse_resumes
    from app.agents.match_agent import batch_match_candidates
    from app.agents.ranking_agent import rank_candidates

    results: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "pipeline": {},
        "metrics": {},
    }

    timeline = []
    total_start = time.time()

    # ---- Step 1: JD 解析 ----
    t0 = time.time()
    jd_profile = await analyze_jd(TEST_JD)
    t1 = time.time() - t0
    timeline.append({"step": "jd_parse", "time": round(t1, 2)})

    # ---- Step 2: 简历解析 ----
    t0 = time.time()
    profiles = await batch_parse_resumes(TEST_RESUMES)
    t2 = time.time() - t0
    timeline.append({"step": "resume_parse", "time": round(t2, 2)})

    ids = list(TEST_RESUMES.keys())
    for i, p in enumerate(profiles):
        p["candidate_id"] = ids[i]

    # ---- Step 3: 匹配评分 ----
    t0 = time.time()
    rubric = jd_profile.pop("rubric", None)
    matches = await batch_match_candidates(jd_profile, profiles, rubric=rubric)
    t3 = time.time() - t0
    timeline.append({"step": "match", "time": round(t3, 2)})

    # ---- Step 4: 排序 ----
    t0 = time.time()
    ranking = await rank_candidates(matches)
    t4 = time.time() - t0
    timeline.append({"step": "rank", "time": round(t4, 2)})

    total_time = time.time() - total_start
    results["pipeline"]["steps"] = timeline
    results["pipeline"]["total_time"] = round(total_time, 2)

    # ---- 提取排序结果 ----
    ranked = ranking.get("ranked_candidates", [])
    results["ranked_ids"] = [c.get("candidate_id", "?") for c in ranked]
    results["scores"] = [
        {
            "candidate_id": c.get("candidate_id", "?"),
            "total_score": c.get("total_score", 0),
            "recommendation": c.get("recommendation", ""),
        }
        for c in ranked
    ]

    # ---- 计算评估指标 ----
    jd_skills = jd_profile.get("required_skills", [])
    relevance = _build_proxy_relevance(jd_skills, TEST_RESUMES)

    for k in [1, 2, 3]:
        p_at_k = precision_at_k(results["ranked_ids"], relevance, k)
        results["metrics"][f"precision_at_{k}"] = round(p_at_k, 4)

    ndcg_3 = ndcg_at_k(results["ranked_ids"], relevance, 3)
    results["metrics"]["ndcg_at_3"] = round(ndcg_3, 4)

    spear = spearman_rank_correlation(results["ranked_ids"], relevance)
    results["metrics"]["spearman_rho"] = round(spear, 4)

    # 分数分布
    scores = [c.get("total_score", 0) for c in ranked]
    if scores:
        results["metrics"]["score_max"] = round(max(scores), 1)
        results["metrics"]["score_min"] = round(min(scores), 1)
        results["metrics"]["score_mean"] = round(sum(scores) / len(scores), 1)
        results["metrics"]["score_range"] = round(max(scores) - min(scores), 1)

    # 代理 ground truth 供参考
    results["proxy_ground_truth"] = {
        "method": "JD 必备技能关键词在简历中的命中率",
        "jd_skills": jd_skills,
        "relevance": {k: round(v, 2) for k, v in relevance.items()},
    }

    return results


def save_results(results: Dict[str, Any], reports_dir: str):
    """
    保存评估结果: .md 报告 + .json 指标。

    参数:
        results: run_evaluation() 的返回值
        reports_dir: 报告保存目录 (evaluation/reports/)
    """
    import pytz

    os.makedirs(reports_dir, exist_ok=True)

    sydney_tz = pytz.timezone("Australia/Sydney")
    now = datetime.now(sydney_tz)
    ts = now.strftime("%Y-%m-%d-%I-%M-%p")
    base = os.path.join(reports_dir, ts)

    # ---- .json 结构化指标 ----
    with open(f"{base}.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # ---- .md 人类可读报告 ----
    steps = results["pipeline"]["steps"]
    total = results["pipeline"]["total_time"]
    metrics = results["metrics"]
    ranked = results["scores"]

    report: List[str] = []
    w = report.append
    w(f"# HireFlow Pipeline 评估报告")
    w(f"")
    w(f"**日期:** {now.strftime('%Y-%m-%d')}  **时间:** {now.strftime('%I:%M %p')}  ")
    w(f"")
    w(f"## 一、Pipeline 性能")
    w(f"")
    w(f"| 步骤 | 耗时 | 占比 |")
    w(f"|------|------|------|")
    for s in steps:
        pct = s["time"] / total * 100 if total > 0 else 0
        w(f"| {s['step']} | {s['time']:.1f}s | {pct:.0f}% |")
    w(f"| **总计** | **{total:.1f}s** | **100%** |")
    w(f"")
    w(f"## 二、评估指标")
    w(f"")
    w(f"| 指标 | 值 | 说明 |")
    w(f"|------|----|------|")
    k_vals = [k for k in sorted(metrics.keys()) if k.startswith("precision_at")]
    for key in k_vals:
        k = key.split("_")[-1]
        w(f"| Precision@{k} | {metrics[key]:.3f} | Top {k} 中真正相关的比例 |")
    w(f"| NDCG@3 | {metrics.get('ndcg_at_3', 0):.3f} | 排序质量 (1=完美) |")
    w(f"| Spearman ρ | {metrics.get('spearman_rho', 0):.3f} | 排序相关性 (-1~1) |")
    w(f"")
    w(f"*注: 当前使用 JD 关键词命中率作为代理 Ground Truth。*  ")
    w(f"*后续需人工标注替换。*")
    w(f"")
    w(f"## 三、候选人排序")
    w(f"")
    w(f"| 排名 | 候选人 | 总分 | 等级 |")
    w(f"|------|--------|------|------|")
    for i, c in enumerate(ranked):
        w(f"| {i+1} | {c['candidate_id']} | {c['total_score']:.0f} | {c['recommendation']} |")
    w(f"")
    w(f"## 四、分数分布")
    w(f"")
    w(f"| 指标 | 值 |")
    w(f"|------|----|")
    w(f"| 最高分 | {metrics.get('score_max', '-')} |")
    w(f"| 最低分 | {metrics.get('score_min', '-')} |")
    w(f"| 平均分 | {metrics.get('score_mean', '-')} |")
    w(f"| 极差 | {metrics.get('score_range', '-')} |")
    w(f"")

    # 观察
    w(f"## 五、观察")
    w(f"")
    if metrics.get("ndcg_at_3", 0) > 0.8:
        w(f"- NDCG@3 = {metrics['ndcg_at_3']:.3f}，排序质量优秀")
    elif metrics.get("ndcg_at_3", 0) > 0.5:
        w(f"- NDCG@3 = {metrics['ndcg_at_3']:.3f}，排序质量一般，有优化空间")
    else:
        w(f"- NDCG@3 = {metrics.get('ndcg_at_3', 0):.3f}，排序质量需改善")
    w(f"- 主要耗时在匹配评分阶段 ({steps[2]['time']:.1f}s, {steps[2]['time']/total*100:.0f}%)")
    w(f"")
    w(f"---")
    w(f"*报告由 run_eval.py 自动生成*")

    with open(f"{base}.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"Report saved: {base}.md + {base}.json")
    return base


# ================================================================
# 命令行入口
# ================================================================

def main():
    """CLI 入口。"""
    print("=" * 50)
    print("  HireFlow 自动化评估")
    print("=" * 50)
    print()

    reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")

    results = asyncio.run(run_evaluation())

    # 打印指标
    m = results["metrics"]
    print(f"\nPipeline: {results['pipeline']['total_time']:.1f}s")
    for k_name in ["precision_at_1", "precision_at_2", "precision_at_3", "ndcg_at_3", "spearman_rho"]:
        if k_name in m:
            print(f"  {k_name}: {m[k_name]:.3f}")
    print(f"  scores: {m.get('score_min', '-')} - {m.get('score_max', '-')} (mean={m.get('score_mean', '-')})")

    # 保存
    save_results(results, reports_dir)
    print("\nDone.")


if __name__ == "__main__":
    main()
