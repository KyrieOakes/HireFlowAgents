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
    <div>
      <h1 className="text-xl font-bold text-gray-800 mb-6">岗位管理</h1>

      {error && <div className="mb-4"><ErrorMessage message={error} /></div>}

      {/* ---- 新建岗位表单 ---- */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6">
        <h2 className="text-sm font-medium text-gray-700 mb-3">新建岗位</h2>
        <div className="mb-3">
          <input
            type="text"
            placeholder="岗位名称 (可选)"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded text-sm mb-2"
          />
          <textarea
            placeholder="粘贴岗位描述 (JD) 全文..."
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            rows={8}
            className="w-full px-3 py-2 border border-gray-300 rounded text-sm font-mono resize-y"
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
        <div className="space-y-3">
          {jobs.map((job) => (
            <div
              key={job.job_id}
              className="bg-white border border-gray-200 rounded-lg p-4"
            >
              <div className="flex items-center justify-between mb-2">
                <div>
                  <span className="font-medium text-gray-800">
                    {job.title || "未命名岗位"}
                  </span>
                  <span className="text-xs text-gray-400 ml-2">{job.job_id}</span>
                  {(job.has_profile || job.jd_profile) && (
                    <span className="ml-2 inline-block px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded">
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
                </div>
              </div>
              {/* 简要信息 */}
              {job.jd_profile && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {job.jd_profile.required_skills?.slice(0, 6).map((s) => (
                    <span key={s} className="px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded">
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
        <div className="fixed inset-0 bg-black/30 z-20 flex items-start justify-center pt-20" onClick={() => setSelectedJob(null)}>
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            {/* 标题栏 */}
            <div className="flex items-center justify-between px-4 py-3 border-b sticky top-0 bg-white">
              <h3 className="font-medium">{selectedJob.title || "岗位详情"}</h3>
              <button onClick={() => setSelectedJob(null)} className="text-gray-400 hover:text-gray-600 text-lg">✕</button>
            </div>
            {/* 内容 */}
            <div className="p-4 space-y-4">
              {/* Rubric 可视化 */}
              {selectedJob.rubric && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-gray-700">评分权重 (Rubric)</h4>
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
                <div className="border border-gray-200 rounded-lg p-3">
                  <div className="text-xs text-gray-400 mb-1">原始 JD 文本</div>
                  <pre className="text-xs text-gray-600 whitespace-pre-wrap">{selectedJob.jd_text}</pre>
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
