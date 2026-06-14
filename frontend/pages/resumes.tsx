// ================================================================
// 简历管理页 — 录入简历 / 解析 / 查看画像
// ================================================================

import { useEffect, useState, useRef } from "react";
import type { Candidate, CandidateProfile } from "@/types";
import {
  listCandidates,
  uploadResume,
  parseResume,
  getCandidate,
} from "@/services/api";
import LoadingButton from "@/components/LoadingButton";
import ErrorMessage from "@/components/ErrorMessage";
import EmptyState from "@/components/EmptyState";
import JsonPanel from "@/components/JsonPanel";

export default function ResumesPage() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [filename, setFilename] = useState("");
  const [resumeText, setResumeText] = useState("");
  const [creating, setCreating] = useState(false);
  const [parsing, setParsing] = useState<Record<string, boolean>>({});
  const [selected, setSelected] = useState<Candidate | null>(null);
  const parsingLock = useRef<Set<string>>(new Set()); // 防抖锁
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { loadCandidates(); }, []);

  async function loadCandidates() {
    setLoading(true);
    setError(null);
    try { setCandidates(await listCandidates()); }
    catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }

  // 上传简历 (无名时自动生成"候选人N")
  async function handleCreate() {
    if (!resumeText.trim()) return;
    setCreating(true);
    setError(null);
    try {
      // 未填姓名时自动生成: 候选人1, 候选人2, ...
      const displayName = name.trim() || `候选人${candidates.length + 1}`;
      await uploadResume(resumeText.trim(), displayName, filename.trim() || undefined);
      setName(""); setFilename(""); setResumeText("");
      await loadCandidates();
    } catch (e: any) { setError(e.message); }
    finally { setCreating(false); }
  }

  // 解析简历 (防抖锁)
  async function handleParse(candidateId: string) {
    if (parsingLock.current.has(candidateId)) return;
    parsingLock.current.add(candidateId);
    setParsing((p) => ({ ...p, [candidateId]: true }));
    setError(null);
    try {
      await parseResume(candidateId);
      await loadCandidates();
    } catch (e: any) { setError(e.message); }
    finally {
      parsingLock.current.delete(candidateId);
      setParsing((p) => ({ ...p, [candidateId]: false }));
    }
  }

  // 查看详情
  async function handleView(candidateId: string) {
    setError(null);
    try { setSelected(await getCandidate(candidateId)); }
    catch (e: any) { setError(e.message); }
  }

  // 读取本地 .txt/.md 文件
  function handleFileRead(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setFilename(file.name);
    const reader = new FileReader();
    reader.onload = () => setResumeText(reader.result as string);
    reader.readAsText(file);
  }

  if (loading) {
    return <div className="text-center text-gray-400 py-12">加载中...</div>;
  }

  return (
    <div>
      <h1 className="text-xl font-bold text-gray-800 mb-6">简历管理</h1>

      {error && <div className="mb-4"><ErrorMessage message={error} /></div>}

      {/* ---- 录入表单 ---- */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6">
        <h2 className="text-sm font-medium text-gray-700 mb-3">录入简历</h2>
        <div className="mb-3 grid grid-cols-1 md:grid-cols-2 gap-2">
          <input
            type="text" placeholder="候选人姓名 (可选)" value={name}
            onChange={(e) => setName(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded text-sm"
          />
          <div className="flex gap-2">
            <input
              type="text" placeholder="文件名 (可选, 如 resume.txt)" value={filename}
              onChange={(e) => setFilename(e.target.value)}
              className="flex-1 px-3 py-2 border border-gray-300 rounded text-sm"
            />
            <button
              onClick={() => fileRef.current?.click()}
              className="px-3 py-2 text-sm text-gray-600 bg-gray-100 border border-gray-300 rounded hover:bg-gray-200 whitespace-nowrap"
            >
              读取文件
            </button>
            <input ref={fileRef} type="file" accept=".txt,.md" onChange={handleFileRead} className="hidden" />
          </div>
        </div>
        <textarea
          placeholder="粘贴简历纯文本 (或点击「读取文件」导入) ..."
          value={resumeText}
          onChange={(e) => setResumeText(e.target.value)}
          rows={10}
          className="w-full px-3 py-2 border border-gray-300 rounded text-sm font-mono resize-y"
        />
        <div className="mt-3">
          <LoadingButton onClick={handleCreate} loading={creating} disabled={!resumeText.trim()}>
            提交简历
          </LoadingButton>
        </div>
      </div>

      {/* ---- 候选人列表 ---- */}
      {candidates.length === 0 ? (
        <EmptyState title="还没有候选人" description="在上方粘贴简历文本来录入第一个候选人" />
      ) : (
        <div className="space-y-3">
          {candidates.map((c) => (
            <div key={c.candidate_id} className="bg-white border border-gray-200 rounded-lg p-4 flex items-center justify-between">
              <div>
                <span className="font-medium text-gray-800">
                  {c.name || c.candidate_id || "未命名"}
                </span>
                <span className="text-xs text-gray-400 ml-2">{c.candidate_id}</span>
                {c.resume_filename && <span className="text-xs text-gray-400 ml-2">📄 {c.resume_filename}</span>}
                {(c.has_profile || c.profile) && (
                  <span className="ml-2 inline-block px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded">已解析</span>
                )}
                {c.profile && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {c.profile.skills?.slice(0, 5).map((s) => (
                      <span key={s} className="px-1.5 py-0.5 bg-gray-100 text-gray-600 text-xs rounded">{s}</span>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex gap-2 flex-shrink-0 ml-4">
                {!(c.has_profile || c.profile) && (
                  <LoadingButton onClick={() => handleParse(c.candidate_id)} loading={!!parsing[c.candidate_id]} variant="secondary">
                    解析
                  </LoadingButton>
                )}
                <LoadingButton onClick={() => handleView(c.candidate_id)} loading={false} variant="secondary">
                  详情
                </LoadingButton>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ---- 候选人详情弹层 ---- */}
      {selected && (
        <div className="fixed inset-0 bg-black/30 z-20 flex items-start justify-center pt-20" onClick={() => setSelected(null)}>
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-4 py-3 border-b sticky top-0 bg-white">
              <h3 className="font-medium">{selected.name || "候选人详情"}</h3>
              <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-600 text-lg">✕</button>
            </div>
            <div className="p-4 space-y-4">
              {/* 基本信息 */}
              {selected.profile && (
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <Info label="姓名" value={selected.profile.name} />
                  <Info label="邮箱" value={selected.profile.email} />
                  <Info label="经验年限" value={selected.profile.estimated_years_of_experience?.toString()} />
                  <Info label="教育" value={`${selected.profile.education?.length || 0} 条`} />
                </div>
              )}
              {/* 完整的 Profile JSON */}
              <JsonPanel title="结构化画像 (CandidateProfile)" data={selected.profile || null} />
              {/* 原始文本 */}
              {selected.resume_text && (
                <div className="border border-gray-200 rounded-lg p-3">
                  <div className="text-xs text-gray-400 mb-1">原始简历文本</div>
                  <pre className="text-xs text-gray-600 whitespace-pre-wrap max-h-48 overflow-auto">{selected.resume_text}</pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Info({ label, value }: { label: string; value?: string }) {
  if (!value) return null;
  return (
    <div>
      <span className="text-gray-400">{label}:</span>{" "}
      <span className="text-gray-700">{value}</span>
    </div>
  );
}
