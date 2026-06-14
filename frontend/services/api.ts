// ================================================================
// HireFlow API 服务层
// 封装所有后端 API 请求，统一处理 URL、JSON 解析和错误
// ================================================================

import type {
  Job,
  JDProfile,
  Candidate,
  CandidateProfile,
  MatchResult,
  RankingResult,
  MatchDetail,
} from "@/types";

// --- 配置 ---
// NEXT_PUBLIC_API_BASE_URL 从环境变量读取，默认指向本地后端
const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

// --- 工具函数 ---

/** 统一 fetch + 错误处理 */
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.json().then((d) => d.detail).catch(() => `${res.status} ${res.statusText}`);
    throw new Error(typeof detail === "string" ? detail : `${res.status} 请求失败`);
  }
  return res.json();
}

// ================================================================
// 岗位 API
// ================================================================

/** 获取所有岗位 */
export async function listJobs(): Promise<Job[]> {
  return request<Job[]>("/jobs/");
}

/** 上传/创建岗位 */
export async function uploadJob(jdText: string, title?: string): Promise<{ job_id: string; title: string | null; message: string }> {
  return request("/jobs/upload", {
    method: "POST",
    body: JSON.stringify({ jd_text: jdText, title }),
  });
}

/** 解析岗位 */
export async function parseJob(jobId: string): Promise<{ job_id: string; jd_profile: JDProfile }> {
  return request(`/jobs/${jobId}/parse`, { method: "POST" });
}

/** 获取岗位详情 */
export async function getJob(jobId: string): Promise<Job> {
  return request(`/jobs/${jobId}`);
}

// ================================================================
// 简历 API
// ================================================================

/** 获取所有候选人 */
export async function listCandidates(): Promise<Candidate[]> {
  return request<Candidate[]>("/resumes/");
}

/** 上传简历文本 */
export async function uploadResume(
  resumeText: string,
  name?: string,
  filename?: string,
): Promise<{ candidate_id: string; name: string | null; message: string }> {
  return request("/resumes/upload", {
    method: "POST",
    body: JSON.stringify({ resume_text: resumeText, name, filename }),
  });
}

/** 解析简历 */
export async function parseResume(candidateId: string): Promise<{ candidate_id: string; profile: CandidateProfile }> {
  return request(`/resumes/${candidateId}/parse`, { method: "POST" });
}

/** 上传 PDF/DOCX/TXT 简历文件 (multipart) */
export async function uploadResumeFile(
  file: File,
  name?: string,
): Promise<{ candidate_id: string; name: string; filename: string; text_length: number; text_preview: string; message: string }> {
  const formData = new FormData();
  formData.append("file", file);
  if (name) formData.append("name", name);
  const url = `${BASE_URL}/resumes/upload-file`;
  const res = await fetch(url, { method: "POST", body: formData });
  if (!res.ok) {
    const detail = await res.json().then((d) => d.detail).catch(() => `${res.status}`);
    throw new Error(typeof detail === "string" ? detail : "上传失败");
  }
  return res.json();
}

/** 获取候选人详情 */
export async function getCandidate(candidateId: string): Promise<Candidate> {
  return request(`/resumes/${candidateId}`);
}

// ================================================================
// 匹配 API
// ================================================================

/** 执行匹配 + 排序 (limit=0 表示全部) */
export async function runMatching(jobId: string, limit: number = 0): Promise<{
  job_id: string;
  total_candidates_in_db: number;
  candidates_matched: number;
  limit: number | null;
  ranking: any;
  match_results: MatchResult[];
}> {
  const params = limit > 0 ? `?limit=${limit}` : "";
  return request(`/jobs/${jobId}/match${params}`, { method: "POST" });
}

/** 获取排名结果 (limit=0 返回全部) */
export async function getRanking(jobId: string, limit: number = 0): Promise<RankingResult> {
  const params = limit > 0 ? `?limit=${limit}` : "";
  return request(`/jobs/${jobId}/ranking${params}`);
}

/** 获取单个候选人详细评分 */
export async function getMatchDetail(jobId: string, candidateId: string): Promise<MatchDetail> {
  return request(`/jobs/${jobId}/candidates/${candidateId}/detail`);
}

// ================================================================
// 删除 API
// ================================================================

/** 删除岗位 */
export async function deleteJob(jobId: string): Promise<{ message: string }> {
  return request(`/jobs/${jobId}`, { method: "DELETE" });
}

/** 删除候选人 */
export async function deleteCandidate(candidateId: string): Promise<{ message: string }> {
  return request(`/resumes/${candidateId}`, { method: "DELETE" });
}
