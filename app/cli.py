#!/usr/bin/env python3
"""
app/cli.py
===========
HireFlow 命令行工具。

不启动 API 服务器，直接在命令行运行完整的招聘筛选流程。
适合快速测试和演示。

用法:
  python -m app.cli run <jd_file> <resume_dir>
  python -m app.cli demo     # 用内置示例数据运行
"""

import sys
import os
import asyncio
import json


def print_banner():
    """打印启动横幅。"""
    print("=" * 60)
    print("  HireFlow - 基于 LangGraph 的多 Agent 招聘筛选系统")
    print("=" * 60)


async def run_pipeline(
    jd_text: str,
    resumes: list[dict],
    verbose: bool = True,
):
    """
    运行完整的招聘筛选流程。

    流程:
    JD上传 → JD解析 → 简历解析 → 匹配评分 → 排序 → 展示结果

    参数:
        jd_text: 岗位描述全文
        resumes: 简历列表 [{"text": "...", "filename": "...", "name": "..."}, ...]
        verbose: 是否打印详细进度
    返回:
        dict: 完整的排序结果
    """
    from app.database.session import init_db, SessionLocal
    from app.database import crud
    from app.agents.jd_agent import analyze_jd
    from app.agents.resume_agent import batch_parse_resumes
    from app.agents.match_agent import batch_match_candidates
    from app.agents.ranking_agent import rank_candidates

    # 初始化数据库
    init_db()
    db = SessionLocal()

    try:
        # ============================================================
        # Step 1: JD 解析
        # ============================================================
        if verbose:
            print("\n[Step 1/5] 正在解析岗位描述...")

        jd_profile = await analyze_jd(jd_text)
        rubric = jd_profile.pop("rubric", None)

        if verbose:
            print(f"  岗位名称: {jd_profile.get('job_title', '未知')}")
            print(f"  必备技能: {', '.join(jd_profile.get('required_skills', []))}")
            print(f"  加分技能: {', '.join(jd_profile.get('preferred_skills', []))}")

        # ============================================================
        # Step 2: 简历解析
        # ============================================================
        if verbose:
            print(f"\n[Step 2/5] 正在解析 {len(resumes)} 份简历...")

        # 构建 {candidate_id: text} 字典
        resume_dict = {}
        for i, resume in enumerate(resumes):
            # 生成简单的 ID
            cid = f"C{str(i+1).zfill(3)}"
            resume_dict[cid] = resume["text"]

            # 也保存到数据库
            crud.create_candidate(
                db=db,
                resume_text=resume["text"],
                name=resume.get("name", ""),
                filename=resume.get("filename", ""),
            )

        candidate_profiles = await batch_parse_resumes(resume_dict)

        # 将 candidate_id 注入每个 profile
        for i, profile in enumerate(candidate_profiles):
            cid = list(resume_dict.keys())[i]
            profile["candidate_id"] = cid
            crud.update_candidate_profile(db, cid, profile)

        if verbose:
            for profile in candidate_profiles:
                print(f"  {profile.get('name', '?')}: {len(profile.get('skills', []))} 项技能, "
                      f"{len(profile.get('education', []))} 条教育, "
                      f"{len(profile.get('projects', []))} 个项目")

        # ============================================================
        # Step 3: 匹配评分
        # ============================================================
        if verbose:
            print(f"\n[Step 3/5] 正在匹配评分...")

        match_results = await batch_match_candidates(
            jd_profile=jd_profile,
            candidate_profiles=candidate_profiles,
            rubric=rubric,
        )

        if verbose:
            for r in match_results:
                print(f"  {r.get('candidate_id', '?')}: {r.get('total_score', 0):.0f} 分 "
                      f"→ {r.get('recommendation', '?')}")

        # ============================================================
        # Step 4: 排序
        # ============================================================
        if verbose:
            print(f"\n[Step 4/5] 正在排序...")

        ranking = await rank_candidates(match_results)

        # ============================================================
        # Step 5: 展示结果
        # ============================================================
        print("\n" + "=" * 60)
        print("  最终排序结果")
        print("=" * 60)

        for i, candidate in enumerate(ranking["ranked_candidates"]):
            score = candidate.get("total_score", 0)
            rec = candidate.get("recommendation", "")
            cid = candidate.get("candidate_id", "?")

            # 根据分数显示不同的符号
            icon = "⭐" if score >= 80 else ("✅" if score >= 65 else ("⚠️" if score >= 50 else "❌"))

            print(f"\n  {icon} 第{i+1}名: {cid}")
            print(f"     总分: {score:.1f} / 100  |  等级: {rec}")

            # 显示各维度分数
            dim_scores = candidate.get("dimension_scores", {})
            if isinstance(dim_scores, dict):
                for dim, val in dim_scores.items():
                    if dim != "risk_penalty":
                        print(f"       {dim}: {val}")

            # 显示优势
            strengths = candidate.get("strengths", [])
            if strengths:
                print(f"      优势: {strengths[0][:60]}..." if len(str(strengths[0])) > 60 else f"      优势: {strengths[0]}")

            # 显示风险
            risks = candidate.get("risks", [])
            if risks:
                print(f"      风险: {risks[0][:60]}..." if len(str(risks[0])) > 60 else f"      风险: {risks[0]}")

        # 统计
        summary = ranking.get("summary", {})
        print(f"\n  📊 统计: {summary.get('total_candidates', 0)} 位候选人")
        print(f"     ⭐ Strong Match: {summary.get('strong_match', 0)}")
        print(f"     ✅ Medium Match: {summary.get('medium_match', 0)}")
        print(f"     ⚠️  Weak Match:   {summary.get('weak_match', 0)}")
        print(f"     ❌ Not Rec:      {summary.get('not_recommended', 0)}")

        # 排序解释
        explanation = ranking.get("explanation", "")
        if explanation:
            print(f"\n  💡 排序说明: {explanation}")

        return ranking

    finally:
        db.close()


async def run_demo():
    """
    使用内置示例数据运行 Demo。

    包含: 1个JD + 3份简历
    """
    # ---- 示例 JD ----
    jd_text = """
岗位名称: 初级 AI 应用开发工程师

岗位职责:
1. 使用 LangChain 和 LangGraph 开发 AI Agent 应用
2. 设计和实现 RAG (检索增强生成) 系统
3. 使用 FastAPI 开发后端 API 服务
4. 参与代码评审和技术文档编写

任职要求:
1. 熟练掌握 Python 编程语言
2. 有 FastAPI 或类似 Web 框架使用经验
3. 了解 Docker 容器化部署
4. 了解 PostgreSQL 或 MySQL 数据库
5. 本科及以上学历，计算机相关专业

加分项:
1. 有 LangChain/LangGraph 实际项目经验
2. 了解 RAG 架构和向量数据库 (如 Qdrant、Chroma)
3. 有 LLM 应用开发经验
4. 了解 Embedding 模型和语义搜索
5. 有开源项目贡献经验

经验要求: 0-3年 (应届生也可)
"""

    # ---- 候选人简历 ----
    resumes = [
        {
            "name": "候选人A",
            "filename": "resume_a.pdf",
            "text": """
姓名: 李明
邮箱: liming@email.com

教育背景:
- 2022-2024 悉尼大学 人工智能 硕士
- 2018-2022 华中科技大学 计算机科学 学士

技能:
Python, FastAPI, Docker, PostgreSQL, LangChain, RAG, Qdrant, Git, PyTorch

项目经历:
- Local RAG System (2024.01-2024.06)
  使用 FastAPI + LangChain + Qdrant 搭建本地 RAG 检索系统
  支持 PDF 上传、文本切分、向量检索和 LLM 问答
  技术栈: FastAPI, LangChain, Qdrant, PyMuPDF, OpenAI API

- AI Chat Assistant (2023.06-2023.12)
  基于 LangGraph 开发的多轮对话 Agent，支持工具调用和记忆管理
  技术栈: LangGraph, LangChain, Python, FastAPI

实习经历:
- 2023.06-2023.09 某AI公司 Python 后端实习生
  参与 RAG 系统开发，负责文档解析和向量存储模块

证书: AWS Cloud Practitioner
""",
        },
        {
            "name": "候选人B",
            "filename": "resume_b.pdf",
            "text": """
姓名: 王芳
邮箱: wangfang@email.com

教育背景:
- 2020-2024 浙江大学 软件工程 学士

技能:
Java, Spring Boot, MySQL, Redis, Docker, Git, Python (基础)

项目经历:
- 电商后台管理系统 (2023.03-2023.08)
  使用 Spring Boot + MySQL + Redis 开发电商后台
  实现了订单管理、用户管理、商品管理等功能

- 校园论坛 (2022.09-2022.12)
  基于 Vue.js + Spring Boot 的校园论坛系统

实习经历:
- 2023.07-2023.12 某互联网公司 Java 开发实习生
  参与后端 API 开发和数据库优化

证书: 无
""",
        },
        {
            "name": "候选人C",
            "filename": "resume_c.pdf",
            "text": """
姓名: 张伟
邮箱: zhangwei@email.com

教育背景:
- 2021-2023 墨尔本大学 数据科学 硕士
- 2017-2021 上海交通大学 数学 学士

技能:
Python, SQL, Scikit-learn, Pandas, NumPy, Docker, FastAPI (学习过), LangChain (学习过)

项目经历:
- 智能简历筛选系统 (2023.06-2023.12)
  使用 Python + Scikit-learn + FastAPI 开发简历自动分类系统
  实现了基于 NLP 的简历信息提取和岗位匹配
  技术栈: Python, FastAPI, Scikit-learn, Pandas

- 数据分析平台 (2022.06-2022.12)
  使用 Python + Pandas + Streamlit 搭建数据分析 Dashboard
  实现数据清洗、可视化和报告生成

实习经历:
- 2023.01-2023.05 某咨询公司 数据分析实习生
  负责数据清洗和可视化报告生成

证书: 无
""",
        },
    ]

    await run_pipeline(jd_text=jd_text, resumes=resumes, verbose=True)


# ================================================================
# 命令行入口
# ================================================================

def main():
    """CLI 入口。"""
    if len(sys.argv) < 2:
        print("用法:")
        print("  python -m app.cli demo      # 用内置示例数据运行")
        print("  python -m app.cli run <jd_file> <resume_dir>  # 用文件运行")
        sys.exit(1)

    command = sys.argv[1]

    if command == "demo":
        print_banner()
        asyncio.run(run_demo())

    elif command == "run":
        if len(sys.argv) < 4:
            print("用法: python -m app.cli run <jd_file> <resume_dir>")
            sys.exit(1)

        jd_file = sys.argv[2]
        resume_dir = sys.argv[3]

        # 读取 JD
        with open(jd_file, "r", encoding="utf-8") as f:
            jd_text = f.read()

        # 读取简历文件夹
        resumes = []
        for filename in os.listdir(resume_dir):
            if filename.endswith((".txt", ".md")):
                filepath = os.path.join(resume_dir, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    text = f.read()
                resumes.append({
                    "text": text,
                    "filename": filename,
                    "name": filename.replace(".txt", "").replace(".md", ""),
                })

        print_banner()
        asyncio.run(run_pipeline(jd_text=jd_text, resumes=resumes))

    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
