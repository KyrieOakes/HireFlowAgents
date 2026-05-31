"""
evaluation/run_ranking_eval.py
===============================
候选人排序评估脚本。

评估 Ranking Agent 的排序质量。
指标:
- Precision@K: 推荐的 Top K 候选人中，真正合适的比例
- NDCG@K: 归一化折损累计增益，考察排序顺序是否合理
- Spearman 秩相关系数: 系统排序和人工排序的相关程度
"""

# TODO: 实现排序评估
# 1. 准备测试数据: 人工标注每个 JD 下候选人的真实排名
# 2. 运行完整匹配+排序流程
# 3. 比较系统排序和人工排序:
#    - Precision@3 = 系统 Top3 中也在人工 Top3 中的人数 / 3
#    - NDCG 越接近 1 说明排序越好
# 4. 输出评估报告


def run_ranking_evaluation():
    """运行排序评估。"""
    pass


if __name__ == "__main__":
    run_ranking_evaluation()
