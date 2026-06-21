// ================================================================
// 岗位管理页 — 创建 JD / 解析 / 查看结构化结果
// ================================================================

import { useEffect, useState, useRef } from "react";
import type { Job, JDProfile, Rubric } from "@/types";
import {
  listJobs,
  uploadJob,
  parseJob,
  getJob,
  deleteJob,
} from "@/services/api";
import LoadingButton from "@/components/LoadingButton";
import ErrorMessage from "@/components/ErrorMessage";
import EmptyState from "@/components/EmptyState";
import JsonPanel from "@/components/JsonPanel";
import ScoreBar from "@/components/ScoreBar";

export default function JobsPage() {
  // 状态
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [jdText, setJdText] = useState("");
  const [title, setTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [parsing, setParsing] = useState<Record<string, boolean>>({});
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  // useRef 同步锁: 防止快速双击触发重复 API 调用
  const parsingLock = useRef<Set<string>>(new Set());

  // 加载岗位列表
  useEffect(() => { loadJobs(); }, []);

  async function loadJobs() {
    setLoading(true);
    setError(null);
    try {
      setJobs(await listJobs());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  // 创建岗位
  async function handleCreate() {
    if (!jdText.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await uploadJob(jdText.trim(), title.trim() || undefined);
      setJdText("");
      setTitle("");
      await loadJobs();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setCreating(false);
    }
  }

  // 解析岗位 (防抖锁: 避免快速双击)
  async function handleParse(jobId: string) {
    // 检查防抖锁: 如果该 jobId 正在解析中, 直接忽略
    if (parsingLock.current.has(jobId)) return;
    // 加锁
    parsingLock.current.add(jobId);
    setParsing((prev) => ({ ...prev, [jobId]: true }));
    setError(null);
    try {
      await parseJob(jobId);
      await loadJobs();
    } catch (e: any) {
      setError(e.message);
    } finally {
      // 解锁
      parsingLock.current.delete(jobId);
      setParsing((prev) => ({ ...prev, [jobId]: false }));
    }
  }

  // 删除岗位
  async function handleDelete(jobId: string, title: string | null) {
    if (!confirm(`确定要删除「${title || jobId}」吗？\n删除后不可恢复。`)) return;
    setError(null);
    try {
      await deleteJob(jobId);
      await loadJobs();
    } catch (e: any) { setError(e.message); }
  }

  // 查看岗位详情
  async function handleView(jobId: string) {
    setError(null);
    try {
      const job = await getJob(jobId);
      setSelectedJob(job);
    } catch (e: any) {
      setError(e.message);
    }
  }

  // 加载中
  if (loading) {
    return <div className="text-center text-gray-400 py-12">加载中...</div>;
  }

  return (
    <div className="space-y-6 soft-enter">
      <div className="glass-pad">
        <p className="section-label">Job Intake</p>
        <h1 className="page-title mt-2">岗位管理</h1>
        <p className="page-subtitle">创建岗位描述，解析结构化 JD 和评分 Rubric，作为后续匹配基准。</p>
      </div>

      {error && <div className="mb-4"><ErrorMessage message={error} /></div>}

      {/* ---- 新建岗位表单 ---- */}
      <div className="glass-pad">
        <div className="mb-4">
          <h2 className="text-base font-semibold text-slate-900">新建岗位</h2>
          <p className="mt-1 text-sm text-slate-500">粘贴 JD 后交给 JD Agent 生成结构化岗位画像。</p>
        </div>
        <div className="mb-3">
          <input
            type="text"
            placeholder="岗位名称 (可选)"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="field mb-2"
          />
          <textarea
            placeholder="粘贴岗位描述 (JD) 全文..."
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            rows={8}
            className="field-mono resize-y"
          />
        </div>
        <LoadingButton onClick={handleCreate} loading={creating} disabled={!jdText.trim()}>
          创建岗位
        </LoadingButton>
      </div>

      {/* ---- 岗位列表 ---- */}
      {jobs.length === 0 ? (
        <EmptyState
          title="还没有岗位"
          description="在上方粘贴岗位描述来创建第一个岗位"
        />
      ) : (
        <div className="grid gap-3">
          {jobs.map((job) => (
            <div
              key={job.job_id}
              className="focus-card p-4"
            >
              <div className="flex items-center justify-between mb-2">
                <div>
                  <span className="font-semibold text-slate-900">
                    {job.title || "未命名岗位"}
                  </span>
                  <span className="ml-2 text-xs text-slate-400">{job.job_id}</span>
                  {(job.has_profile || job.jd_profile) && (
                    <span className="chip-green ml-2">
                      已解析
                    </span>
                  )}
                </div>
                <div className="flex gap-2">
                  {!(job.has_profile || job.jd_profile) && (
                    <LoadingButton
                      onClick={() => handleParse(job.job_id)}
                      loading={!!parsing[job.job_id]}
                      variant="secondary"
                    >
                      解析 JD
                    </LoadingButton>
                  )}
                  <LoadingButton
                    onClick={() => handleView(job.job_id)}
                    loading={false}
                    variant="secondary"
                  >
                    查看详情
                  </LoadingButton>
                  <LoadingButton
                    onClick={() => handleDelete(job.job_id, job.title)}
                    loading={false}
                    variant="danger"
                  >
                    删除
                  </LoadingButton>
                </div>
              </div>
              {/* 简要信息 */}
              {job.jd_profile && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {job.jd_profile.required_skills?.slice(0, 6).map((s) => (
                    <span key={s} className="chip-blue">
                      {s}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ---- 岗位详情弹层 ---- */}
      {selectedJob && (
        <div className="fixed inset-0 z-20 flex items-start justify-center bg-slate-950/35 px-4 pt-20 backdrop-blur-sm" onClick={() => setSelectedJob(null)}>
          <div className="glass-panel soft-pop max-h-[80vh] w-full max-w-2xl overflow-auto" onClick={(e) => e.stopPropagation()}>
            {/* 标题栏 */}
            <div className="sticky top-0 flex items-center justify-between border-b border-slate-200 bg-white/80 px-4 py-3 backdrop-blur">
              <h3 className="font-semibold text-slate-900">{selectedJob.title || "岗位详情"}</h3>
              <button onClick={() => setSelectedJob(null)} className="text-lg text-slate-400 transition hover:text-slate-700">×</button>
            </div>
            {/* 内容 */}
            <div className="p-4 space-y-4">
              {/* Rubric 可视化 */}
              {selectedJob.rubric && (
                <div className="space-y-2">
                  <h4 className="text-sm font-semibold text-slate-700">评分权重 (Rubric)</h4>
                  {Object.entries(selectedJob.rubric)
                    .filter(([k]) => k !== "total")
                    .map(([key, val]: [string, any]) => (
                      <ScoreBar
                        key={key}
                        label={rubricLabel(key)}
                        score={val.max_score}
                        maxScore={30}
                      />
                    ))}
                </div>
              )}
              {/* JD Profile */}
              <JsonPanel title="结构化 JD (JobDescription)" data={selectedJob.jd_profile || null} />
              {/* 原始文本 */}
              {selectedJob.jd_text && (
                <div className="rounded-lg border border-slate-200 bg-white/70 p-3">
                  <div className="mb-1 text-xs text-slate-400">原始 JD 文本</div>
                  <pre className="whitespace-pre-wrap text-xs text-slate-600">{selectedJob.jd_text}</pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Rubric 字段的中文标签
function rubricLabel(key: string): string {
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
