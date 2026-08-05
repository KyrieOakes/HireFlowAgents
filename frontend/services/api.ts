// ================================================================
// HireFlow API 服务层
// 封装所有后端 API 请求，统一处理 URL、JSON 解析和错误
// ================================================================

import type {
  Job,
  JDProfile,
  Candidate,
  CandidateProfile,
  RankingResult,
  MatchDetail,
  InterviewQuestion,
  InterviewEvaluation,
  EmailDraft,
  AgentFailureAction,
  MatchingRunResponse,
  WorkflowResponse,
  WorkflowResumeAction,
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

/** 人工修改岗位名称，并同步后端结构化 JD */
export async function updateJobTitle(
  jobId: string,
  title: string,
): Promise<{ job_id: string; title: string; jd_profile?: JDProfile | null; message: string }> {
  return request(`/jobs/${jobId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
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

/** 人工修改候选人姓名，并同步后端结构化画像 */
export async function updateCandidateName(
  candidateId: string,
  name: string,
): Promise<{ candidate_id: string; name: string; profile?: CandidateProfile | null; message: string }> {
  return request(`/resumes/${candidateId}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
}

// ================================================================
// 匹配 API
// ================================================================

/** 执行 Evidence ReAct Agent + 匹配 + 排序。 */
export async function runMatching(
  jobId: string,
  limit: number = 0,
  agentFailureAction: AgentFailureAction = "ask_user",
): Promise<MatchingRunResponse> {
  // URLSearchParams 会正确编码参数，避免手工拼接多个问号或特殊字符。
  const params = new URLSearchParams();
  if (limit > 0) params.set("limit", String(limit));
  params.set("agent_failure_action", agentFailureAction);
  return request(`/jobs/${jobId}/match?${params.toString()}`, { method: "POST" });
}

/** 启动 LangGraph 主匹配流程，并运行到证据审核或最终排名审核中断点。 */
export async function startMatchingWorkflow(
  jobId: string,
  limit: number = 0,
): Promise<WorkflowResponse> {
  return request("/workflow/run", {
    method: "POST",
    body: JSON.stringify({ job_id: jobId, limit }),
  });
}

/** 提交人工决定，让 LangGraph 从 PostgreSQL checkpoint 恢复执行。 */
export async function resumeMatchingWorkflow(
  threadId: string,
  action: WorkflowResumeAction,
  selectedCandidateIds: string[] = [],
  comment: string = "",
): Promise<WorkflowResponse> {
  return request(`/workflow/${threadId}/resume`, {
    method: "POST",
    body: JSON.stringify({
      action,
      selected_candidate_ids: selectedCandidateIds,
      comment,
    }),
  });
}

/** 读取持久化工作流，页面刷新后仍可恢复审核现场。 */
export async function getMatchingWorkflowState(threadId: string): Promise<WorkflowResponse> {
  return request(`/workflow/${threadId}/state`);
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
// 面试 / 评价 / 邮件 API
// ================================================================

/** 生成候选人的面试问题 */
export async function generateInterviewQuestions(
  jobId: string,
  candidateId: string,
): Promise<{ job_id: string; candidate_id: string; questions: InterviewQuestion[] }> {
  return request(`/jobs/${jobId}/candidates/${candidateId}/questions`, {
    method: "POST",
  });
}

/** 获取候选人的面试问题 */
export async function getInterviewQuestions(
  jobId: string,
  candidateId: string,
): Promise<{ job_id: string; candidate_id: string; questions: InterviewQuestion[] }> {
  return request(`/jobs/${jobId}/candidates/${candidateId}/questions`);
}

/** 提交面试反馈并生成结构化评价 */
export async function submitInterviewEvaluation(
  jobId: string,
  candidateId: string,
  interviewFeedback: string,
): Promise<{ job_id: string; candidate_id: string; evaluation: InterviewEvaluation }> {
  return request(`/jobs/${jobId}/candidates/${candidateId}/evaluate`, {
    method: "POST",
    body: JSON.stringify({ interview_feedback: interviewFeedback }),
  });
}

/** 获取候选人的结构化面试评价 */
export async function getInterviewEvaluation(
  jobId: string,
  candidateId: string,
): Promise<{
  job_id: string;
  candidate_id: string;
  feedback_text: string;
  evaluation: InterviewEvaluation;
  final_recommendation: string;
}> {
  return request(`/jobs/${jobId}/candidates/${candidateId}/evaluation`);
}

/** 生成 HR 邮件草稿 */
export async function createEmailDraft(
  jobId: string,
  candidateId: string,
  emailType: "interview_invite" | "rejection" | "follow_up" | "next_round",
): Promise<EmailDraft & { job_id: string; candidate_id: string; message?: string }> {
  return request(`/jobs/${jobId}/candidates/${candidateId}/email-draft`, {
    method: "POST",
    body: JSON.stringify({ email_type: emailType }),
  });
}

/** 获取候选人的邮件草稿列表 */
export async function getEmailDrafts(
  jobId: string,
  candidateId: string,
): Promise<{ job_id: string; candidate_id: string; drafts: EmailDraft[] }> {
  return request(`/jobs/${jobId}/candidates/${candidateId}/email-draft`);
}

/** 批准邮件草稿；系统只改状态，不发送邮件 */
export async function approveEmailDraft(emailId: string): Promise<{ email_id: string; status: string; message: string }> {
  return request(`/email-drafts/${emailId}/approve`, { method: "POST" });
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
