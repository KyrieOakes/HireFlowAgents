"""
evaluation/run_parsing_eval.py
===============================
简历解析评估脚本。

评估 Resume Agent 和 JD Agent 的信息提取准确度。
指标:
- Field Accuracy: 字段级别的提取准确率
- Skill Extraction Precision/Recall: 技能提取的精确率和召回率
"""

# TODO: 实现简历解析评估
# 1. 加载标注好的 ground truth 数据集
#    (人工标注: "这份简历里有哪些技能/教育经历/项目")
# 2. 运行 Resume Agent 解析简历
# 3. 比较 Agent 输出和 ground truth:
#    - Precision = 正确提取的技能数 / Agent 提取的总技能数
#    - Recall = 正确提取的技能数 / 简历中实际的总技能数
# 4. 输出评估报告


def run_parsing_evaluation():
    """运行简历解析评估。"""
    pass


if __name__ == "__main__":
    run_parsing_evaluation()
