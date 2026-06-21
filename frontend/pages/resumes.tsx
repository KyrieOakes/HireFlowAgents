// ================================================================
// 简历管理页 — 录入简历 / 解析 / 查看画像
// ================================================================

import { useEffect, useState, useRef } from "react";
import type { Candidate, CandidateProfile } from "@/types";
import {
  listCandidates,
  uploadResume,
  uploadResumeFile,
  parseResume,
  getCandidate,
  deleteCandidate,
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
  // 文件上传状态
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadPreview, setUploadPreview] = useState(""); // 上传后显示提取的文本预览
  const fileRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null); // 候选人列表区域引用, 用于滚动

  useEffect(() => { loadCandidates(); }, []);

  // 打开详情弹窗时支持 Esc 关闭；滚动交给弹层遮罩自身处理，避免页面被锁死。
  useEffect(() => {
    if (!selected) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSelected(null);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [selected]);

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

  // 上传 PDF/DOCX/TXT 文件 → 自动提取文本 → 自动解析 → 滚动到列表
  async function handleFileUpload() {
    if (!uploadFile) return;
    setUploading(true);
    setError(null);
    try {
      // Step 1: 上传文件, 后端提取文本
      const result = await uploadResumeFile(uploadFile, name.trim() || undefined);
      const newCandidateId = result.candidate_id;
      setUploadPreview(result.text_preview);
      setUploadFile(null);
      setName(""); setFilename("");

      // Step 2: 刷新候选人列表 (新候选人出现在列表中)
      await loadCandidates();

      // Step 3: 自动触发解析 (按钮显示"解析中")
      if (!parsingLock.current.has(newCandidateId)) {
        parsingLock.current.add(newCandidateId);
        setParsing((p) => ({ ...p, [newCandidateId]: true }));
        try {
          await parseResume(newCandidateId);
          await loadCandidates(); // 解析完成后刷新, 显示"已解析"和技能标签
        } catch (e: any) { /* 解析失败不阻塞, 用户可手动重试 */ }
        finally {
          parsingLock.current.delete(newCandidateId);
          setParsing((p) => ({ ...p, [newCandidateId]: false }));
        }
      }

      // Step 4: 滚动到候选人列表区域
      setTimeout(() => {
        listRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 200);

    } catch (e: any) { setError(e.message); }
    finally { setUploading(false); }
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

  // 删除候选人
  async function handleDelete(candidateId: string, displayName: string | null) {
    if (!confirm(`确定要删除「${displayName || candidateId}」吗？\n删除后不可恢复。`)) return;
    setError(null);
    try {
      await deleteCandidate(candidateId);
      await loadCandidates();
    } catch (e: any) { setError(e.message); }
  }

  // 查看详情
  async function handleView(candidateId: string) {
    setError(null);
    try { setSelected(await getCandidate(candidateId)); }
    catch (e: any) { setError(e.message); }
  }

  // 读取本地 .txt/.md 文件
  // TXT/MD 文本文件读取 (用于粘贴区)
  function handleFileRead(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    // 如果是 PDF/DOCX → 走文件上传流程
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (ext === "pdf" || ext === "docx") {
      setUploadFile(file);
      setFilename(file.name);
      return;
    }
    // TXT/MD → 读取为文本填入编辑区
    setFilename(file.name);
    const reader = new FileReader();
    reader.onload = () => setResumeText(reader.result as string);
    reader.readAsText(file);
  }

  if (loading) {
    return <div className="text-center text-gray-400 py-12">加载中...</div>;
  }

  return (
    <div className="space-y-6 soft-enter">
      <div className="glass-pad">
        <p className="section-label">Candidate Intake</p>
        <h1 className="page-title mt-2">简历管理</h1>
        <p className="page-subtitle">上传简历文件或粘贴文本，解析候选人画像并为 RAG 证据检索建立索引。</p>
      </div>

      {error && <div className="mb-4"><ErrorMessage message={error} /></div>}

      {/* ---- 录入表单 ---- */}
      <div className="glass-pad">
        <div className="mb-4">
          <h2 className="text-base font-semibold text-slate-900">录入简历</h2>
          <p className="mt-1 text-sm text-slate-500">支持 PDF、DOCX、TXT、MD，文件上传后可自动触发解析。</p>
        </div>

        {/* ---- PDF/DOCX 文件上传区 ---- */}
        <div
          className="mb-4 cursor-pointer rounded-lg border-2 border-dashed border-slate-300 bg-white/55 p-6 text-center backdrop-blur transition duration-200 hover:-translate-y-0.5 hover:border-sky-400 hover:bg-sky-50/60"
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add("border-blue-500","bg-blue-50"); }}
          onDragLeave={(e) => { e.currentTarget.classList.remove("border-blue-500","bg-blue-50"); }}
          onDrop={(e) => {
            e.preventDefault();
            e.currentTarget.classList.remove("border-blue-500","bg-blue-50");
            const f = e.dataTransfer.files?.[0];
            if (f) {
              const ext = f.name.split(".").pop()?.toLowerCase();
              if (ext === "pdf" || ext === "docx") { setUploadFile(f); setFilename(f.name); }
              else { const r = new FileReader(); r.onload = () => setResumeText(r.result as string); r.readAsText(f); setFilename(f.name); }
            }
          }}
        >
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-lg border border-slate-200 bg-white/80 text-sm font-semibold text-slate-500 shadow-sm">CV</div>
          <p className="text-sm text-slate-600">
            <span className="font-medium text-sky-700">点击选择</span> 或拖拽 PDF / DOCX / TXT 文件到此处
          </p>
          <p className="mt-1 text-xs text-slate-400">支持 PDF, DOCX, TXT, MD 格式</p>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.txt,.md"
            onChange={handleFileRead}
            className="hidden"
          />
        </div>

        {/* 已选文件提示 */}
        {uploadFile && (
          <div className="mb-4 flex items-center justify-between rounded-lg border border-sky-200 bg-sky-50/80 p-3">
            <div className="flex items-center gap-2">
              <span className="chip-blue">文件</span>
              <span className="text-sm text-slate-700">{uploadFile.name}</span>
              <span className="text-xs text-slate-400">({(uploadFile.size / 1024).toFixed(0)} KB)</span>
            </div>
            <div className="flex gap-2">
              <LoadingButton onClick={handleFileUpload} loading={uploading} disabled={!uploadFile}>
                上传并解析
              </LoadingButton>
              <button onClick={() => { setUploadFile(null); setFilename(""); }} className="px-3 py-2 text-sm text-slate-500 hover:text-slate-700">
                取消
              </button>
            </div>
          </div>
        )}

        {/* 上传后文本预览 */}
        {uploadPreview && (
          <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50/80 p-3">
            <p className="mb-1 text-xs font-medium text-emerald-700">文件上传成功，已自动提取文本:</p>
            <pre className="max-h-24 overflow-auto whitespace-pre-wrap text-xs text-emerald-800">{uploadPreview}</pre>
          </div>
        )}

        {/* ---- 文本粘贴区 ---- */}
        <div className="mt-2 border-t border-slate-200 pt-4">
          <p className="mb-2 text-xs text-slate-400">或手动粘贴简历文本:</p>
          <div className="mb-3 grid grid-cols-1 md:grid-cols-2 gap-2">
            <input
              type="text" placeholder="候选人姓名 (可选, 匿名简历自动命名)" value={name}
              onChange={(e) => setName(e.target.value)}
              className="field"
            />
            <input
              type="text" placeholder="文件名 (可选)" value={filename}
              onChange={(e) => setFilename(e.target.value)}
              className="field"
            />
          </div>
          <textarea
            placeholder="粘贴简历纯文本..."
            value={resumeText}
            onChange={(e) => setResumeText(e.target.value)}
            rows={8}
            className="field-mono resize-y"
          />
          <div className="mt-3">
            <LoadingButton onClick={handleCreate} loading={creating} disabled={!resumeText.trim()}>
              提交文本
            </LoadingButton>
          </div>
        </div>
      </div>

      {/* ---- 候选人列表 ---- */}
      {candidates.length === 0 ? (
        <EmptyState title="还没有候选人" description="在上方粘贴简历文本来录入第一个候选人" />
      ) : (
        <div ref={listRef} className="grid gap-3">
          {candidates.map((c) => (
            <div key={c.candidate_id} className="focus-card flex items-center justify-between p-4">
              <div>
                <span className="font-semibold text-slate-900">
                  {c.name || c.candidate_id || "未命名"}
                </span>
                <span className="ml-2 text-xs text-slate-400">{c.candidate_id}</span>
                {c.resume_filename && <span className="ml-2 text-xs text-slate-400">{c.resume_filename}</span>}
                {(c.has_profile || c.profile) && (
                  <span className="chip-green ml-2">已解析</span>
                )}
                {c.profile && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {c.profile.skills?.slice(0, 5).map((s) => (
                      <span key={s} className="chip">{s}</span>
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
                <LoadingButton onClick={() => handleDelete(c.candidate_id, c.name)} loading={false} variant="danger">
                  删除
                </LoadingButton>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ---- 候选人详情弹层 ---- */}
      {selected && (
        <div className="fixed inset-0 z-[100] overflow-y-auto bg-slate-950/35 px-4 py-20 backdrop-blur-sm sm:py-24" onClick={() => setSelected(null)}>
          <div className="glass-panel soft-pop mx-auto w-full max-w-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 flex items-center justify-between border-b border-slate-200 bg-white/80 px-4 py-3 backdrop-blur">
              <h3 className="font-semibold text-slate-900">{selected.name || "候选人详情"}</h3>
              <button onClick={() => setSelected(null)} className="text-lg text-slate-400 transition hover:text-slate-700">×</button>
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
                <div className="rounded-lg border border-slate-200 bg-white/70 p-3">
                  <div className="mb-1 text-xs text-slate-400">原始简历文本</div>
                  <pre className="max-h-48 overflow-auto whitespace-pre-wrap text-xs text-slate-600">{selected.resume_text}</pre>
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
      <span className="text-slate-400">{label}:</span>{" "}
      <span className="text-slate-700">{value}</span>
    </div>
  );
}
