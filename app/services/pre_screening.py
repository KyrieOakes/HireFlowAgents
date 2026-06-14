"""
app/services/pre_screening.py
===============================
候选人粗筛服务 (Stage 1: 关键词匹配)。

在两阶段排序中作为第一阶段:
  Stage 1 (粗筛): 关键词匹配 → 快速过滤, 零LLM调用
  Stage 2 (精排): LLM 多维度评分 → 仅对粗筛后的Top K候选

算法:
  对每个候选人计算"技能匹配分":
    required_score = 命中的必备技能数 / JD必备技能总数 × 70
    preferred_score = 命中的加分技能数 / JD加分技能总数 × 30
    total = required_score + preferred_score

  返回粗筛分最高的 top_k 个候选人。
"""

from typing import List, Dict, Any, Tuple


def pre_screen_candidates(
    jd_profile: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    top_k: int = 15,
) -> List[Dict[str, Any]]:
    """
    对候选人进行快速粗筛，返回 top_k 个候选人。

    使用纯关键词匹配，不调用 LLM，速度极快 (< 1ms/人)。

    参数:
        jd_profile: 结构化岗位信息 (含 required_skills, preferred_skills)
        candidates: 候选人列表, 每个需含 skills 字段
        top_k: 保留前几名进入精排 (默认15)
    返回:
        List[dict]: 按粗筛分降序排列的 top_k 候选人 (附加 _prescore 字段)
    """
    required = set(s.lower() for s in jd_profile.get("required_skills", []))
    preferred = set(s.lower() for s in jd_profile.get("preferred_skills", []))

    # 如果 JD 没有技能信息，跳过粗筛，全部返回
    if not required and not preferred:
        return candidates[:top_k]

    scored: List[Tuple[float, Dict[str, Any]]] = []

    for c in candidates:
        candidate_skills = set(s.lower() for s in c.get("skills", []))

        # 计算必备技能命中率
        req_hits = len(required & candidate_skills)
        req_score = (req_hits / len(required) * 70) if required else 35

        # 计算加分技能命中率
        pref_hits = len(preferred & candidate_skills)
        pref_score = (pref_hits / len(preferred) * 30) if preferred else 15

        total = req_score + pref_score

        # 附加粗筛分到候选人的副本中 (不修改原对象)
        c_copy = dict(c)
        c_copy["_prescore"] = round(total, 1)
        c_copy["_req_hits"] = req_hits
        c_copy["_pref_hits"] = pref_hits

        scored.append((total, c_copy))

    # 按粗筛分降序排列
    scored.sort(key=lambda x: x[0], reverse=True)

    # 返回 top_k
    result = [c for _, c in scored[:top_k]]

    return result
