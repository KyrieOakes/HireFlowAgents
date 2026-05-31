"""
evaluation/run_rag_eval.py
===========================
RAG 证据评估脚本。

评估检索到的简历证据是否准确、忠实。
指标:
- Context Precision: 检索到的内容是否与查询相关
- Faithfulness: 评分断言是否被检索到的证据支持
- Evidence Coverage: 有多少评分维度有证据支撑
"""

# TODO: 实现 RAG 评估
# 1. 准备评估用的问题-答案-证据三元组
# 2. 运行 RAG 检索
# 3. 评估每个检索到的证据:
#    - Faithfulness: 检查 Match Agent 的 claim 和 evidence.text 是否一致
#    - Coverage: 有多少 claim 有对应的 evidence
# 4. 输出评估报告


def run_rag_evaluation():
    """运行 RAG 证据评估。"""
    pass


if __name__ == "__main__":
    run_rag_evaluation()
