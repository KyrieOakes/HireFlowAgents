// ================================================================
// 匹配排名页 — 选择岗位 → 触发匹配 → 展示排名 + 详情
// ================================================================

import { useEffect, useState, useRef } from "react";
import type { Job, RankedCandidate, MatchDetail } from "@/types";
import { listJobs, runMatching, getRanking, getMatchDetail } from "@/services/api";
import LoadingButton from "@/components/LoadingButton";
import ErrorMessage from "@/components/ErrorMessage";
import EmptyState from "@/components/EmptyState";
import StatusBadge from "@/components/StatusBadge";
import ScoreBar from "@/components/ScoreBar";

export default function MatchingPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string>("");
  const [matching, setMatching] = useState(false);
  const matchLock = useRef(false);        // 匹配防抖锁
  const detailLock = useRef<Set<string>>(new Set()); // 详情防抖锁
  const [ranked, setRanked] = useState<RankedCandidate[]>([]);
  const [detail, setDetail] = useState<MatchDetail | null>(null);
  const [detailId, setDetailId] = useState<string>("");
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        setJobs(await listJobs());
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // 执行匹配 (防抖锁)
  async function handleMatch() {
    if (!selectedJobId || matchLock.current) return;
    matchLock.current = true;
    setMatching(true);
    setError(null);
    setRanked([]);
    try {
      const res = await runMatching(selectedJobId);
      const rankRes = await getRanking(selectedJobId);
      setRanked(rankRes.ranked_candidates);
    } catch (e: any) {
      setError(e.message);
    } finally {
      matchLock.current = false;
      setMatching(false);
    }
  }

  // 查看候选人详情 (防抖锁)
  async function handleDetail(candidateId: string) {
    if (!selectedJobId || detailLock.current.has(candidateId)) return;
    detailLock.current.add(candidateId);
    setDetailLoading(true);
    setDetailId(candidateId);
    setError(null);
    try {
      setDetail(await getMatchDetail(selectedJobId, candidateId));
    } catch (e: any) {
      setError(e.message);
    } finally {
      detailLock.current.delete(candidateId);
      setDetailLoading(false);
    }
  }

  if (loading) {
    return <div className="text-center text-gray-400 py-12">加载中...</div>;
  }

  return (
    <div>
      <h1 className="text-xl font-bold text-gray-800 mb-6">匹配与排名</h1>

      {error && <div className="mb-4"><ErrorMessage message={error} /></div>}

      {/* ---- 选择岗位 + 触发匹配 ---- */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6">
        <h2 className="text-sm font-medium text-gray-700 mb-3">执行匹配</h2>
        <div className="flex gap-3 items-end flex-wrap">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-xs text-gray-500 mb-1">选择岗位</label>
            <select
              value={selectedJobId}
              onChange={(e) => setSelectedJobId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
            >
              <option value="">— 请选择已解析的岗位 —</option>
              {jobs.filter((j) => (j.has_profile || j.jd_profile)).map((j) => (
                <option key={j.job_id} value={j.job_id}>{j.title || j.job_id}</option>
              ))}
            </select>
          </div>
          <LoadingButton onClick={handleMatch} loading={matching} disabled={!selectedJobId}>
            开始匹配
          </LoadingButton>
        </div>
        {jobs.filter((j) => (j.has_profile || j.jd_profile)).length === 0 && (
          <p className="text-xs text-gray-400 mt-2">还没有已解析的岗位，请先到「岗位管理」创建并解析JD。</p>
        )}
      </div>

      {/* ---- 排序结果 ---- */}
      {ranked.length === 0 ? (
        <EmptyState title="还没有排名结果" description="选择一个岗位后点击「开始匹配」" />
      ) : (
        <>
          <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">排名结果</h2>
          <div className="space-y-4">
            {ranked.map((c, i) => (
              <div key={c.candidate_id} className="bg-white border border-gray-200 rounded-lg p-4">
                {/* 头部: 排名 + ID + 分数 + 等级 */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    {/* 排名数字 */}
                    <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white ${
                      i === 0 ? "bg-yellow-500" : i === 1 ? "bg-gray-400" : i === 2 ? "bg-amber-600" : "bg-gray-300"
                    }`}>
                      {c.rank}
                    </span>
                    <div>
                      <span className="font-medium text-gray-800">{c.candidate_id}</span>
                      <span className="text-xs text-gray-400 ml-2">总分</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-lg font-bold text-gray-800">{c.total_score}<span className="text-sm font-normal text-gray-400">/100</span></span>
                    <StatusBadge level={c.recommendation} />
                  </div>
                </div>

                {/* 分数条 */}
                <ScoreBar score={c.total_score} />

                {/* 优势 + 风险 */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                  {/* 优势 */}
                  <div>
                    <div className="text-xs text-green-600 font-medium mb-1">✅ 优势</div>
                    {c.strengths?.length > 0 ? (
                      <ul className="text-xs text-gray-600 space-y-0.5">
                        {c.strengths.slice(0, 2).map((s, idx) => (
                          <li key={idx} className="truncate">{s}</li>
                        ))}
                      </ul>
                    ) : <span className="text-xs text-gray-400">暂无</span>}
                  </div>
                  {/* 风险 */}
                  <div>
                    <div className="text-xs text-red-500 font-medium mb-1">⚠️ 风险</div>
                    {c.risks?.length > 0 ? (
                      <ul className="text-xs text-gray-600 space-y-0.5">
                        {c.risks.slice(0, 2).map((r, idx) => (
                          <li key={idx} className="truncate">{r}</li>
                        ))}
                      </ul>
                    ) : <span className="text-xs text-gray-400">暂无</span>}
                  </div>
                </div>

                {/* 查看详情按钮 */}
                <div className="mt-3 text-right">
                  <LoadingButton
                    onClick={() => handleDetail(c.candidate_id)}
                    loading={detailLoading && detailId === c.candidate_id}
                    variant="secondary"
                  >
                    详细评分
                  </LoadingButton>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* ---- 候选人详细评分弹层 ---- */}
      {detail && (
        <div className="fixed inset-0 bg-black/30 z-20 flex items-start justify-center pt-20" onClick={() => setDetail(null)}>
          <div className="bg-white rounded-lg shadow-xl max-w-xl w-full mx-4 max-h-[80vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-4 py-3 border-b sticky top-0 bg-white">
              <h3 className="font-medium">详细评分</h3>
              <button onClick={() => setDetail(null)} className="text-gray-400 hover:text-gray-600 text-lg">✕</button>
            </div>
            <div className="p-4 space-y-4">
              {/* 总分 + 等级 */}
              <div className="flex items-center gap-3">
                <span className="text-2xl font-bold text-gray-800">{detail.total_score}</span>
                <span className="text-sm text-gray-400">/ 100</span>
                <StatusBadge level={detail.recommendation} />
              </div>

              {/* 各维度分数 */}
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">维度得分</h4>
                <div className="space-y-1.5">
                  {detail.dimension_scores && Object.entries(detail.dimension_scores).map(([key, val]) => (
                    <ScoreBar key={key} label={dimLabel(key)} score={val} maxScore={30} />
                  ))}
                </div>
              </div>

              {/* 证据 */}
              {detail.evidence && detail.evidence.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2">支撑证据</h4>
                  <div className="space-y-2">
                    {detail.evidence.map((ev, i) => (
                      <div key={i} className="bg-gray-50 rounded p-2 text-xs">
                        <div className="text-gray-700 font-medium">{ev.claim}</div>
                        <div className="text-gray-500 mt-0.5">{ev.text}</div>
                        <div className="text-gray-400 mt-0.5">来源: {ev.source}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 优势+风险 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <h4 className="text-sm font-medium text-green-700 mb-1">优势</h4>
                  <ul className="text-xs text-gray-600 space-y-0.5">
                    {detail.strengths?.map((s, i) => <li key={i}>✅ {s}</li>) || <li className="text-gray-400">暂无</li>}
                  </ul>
                </div>
                <div>
                  <h4 className="text-sm font-medium text-red-600 mb-1">风险</h4>
                  <ul className="text-xs text-gray-600 space-y-0.5">
                    {detail.risks?.map((r, i) => <li key={i}>⚠️ {r}</li>) || <li className="text-gray-400">暂无</li>}
                  </ul>
                </div>
              </div>

              {/* 总结 */}
              {detail.summary && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-1">匹配总结</h4>
                  <p className="text-sm text-gray-600">{detail.summary}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/** 维度字段 → 中文 */
function dimLabel(key: string): string {
  const map: Record<string, string> = {
    technical_skills: "技术技能",
    project_relevance: "项目相关性",
    experience: "工作经验",
    education: "教育背景",
    domain_relevance: "领域相关性",
    communication: "沟通表达",
    risk_penalty: "风险扣分",
  };
  return map[key] || key;
}
