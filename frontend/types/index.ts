// ================================================================
// HireFlow 前端 TypeScript 类型定义
// ================================================================

/** 岗位信息 */
export interface Job {
  job_id: string;
  title: string | null;
  jd_text?: string;
  jd_profile?: JDProfile | null;
  rubric?: Rubric | null;
  // 列表 API 返回 has_profile 标志 (不返回完整 profile 避免数据过大)
  has_profile?: boolean;
}

/** JD 结构化解析结果 */
export interface JDProfile {
  job_title: string;
  required_skills: string[];
  preferred_skills: string[];
  responsibilities: string[];
  education_requirements: string[];
  experience_requirements?: string;
  technical_requirements: string[];
  soft_skills: string[];
  company?: string;
  location?: string;
}

/** 评分 Rubric */
export interface Rubric {
  technical_skills: { max_score: number; weight: number };
  project_relevance: { max_score: number; weight: number };
  experience: { max_score: number; weight: number };
  education: { max_score: number; weight: number };
  domain_relevance: { max_score: number; weight: number };
  communication: { max_score: number; weight: number };
  risk_penalty: { max_score: number; weight: number };
  total: number;
}

/** 候选人基本信息 */
export interface Candidate {
  candidate_id: string;
  name: string | null;
  email?: string | null;
  resume_filename?: string | null;
  resume_text?: string;
  profile?: CandidateProfile | null;
  // 列表 API 返回 has_profile 标志
  has_profile?: boolean;
}

/** 候选人结构化画像 */
export interface CandidateProfile {
  candidate_id: string;
  name: string;
  email?: string;
  phone?: string;
  education: Education[];
  skills: string[];
  projects: Project[];
  work_experience: WorkExperience[];
  certifications: string[];
  strengths: string[];
  risks: string[];
  missing_info: string[];
  estimated_years_of_experience?: number;
}

export interface Education {
  degree: string;
  school: string;
  major: string;
  start_year?: number;
  end_year?: number;
}

export interface Project {
  name: string;
  description: string;
  technologies: string[];
  role?: string;
}

export interface WorkExperience {
  company: string;
  title: string;
  duration?: string;
  description: string[];
}

/** 维度分数 */
export interface DimensionScores {
  technical_skills: number;
  project_relevance: number;
  experience: number;
  education: number;
  domain_relevance: number;
  communication: number;
  risk_penalty: number;
}

/** 匹配结果 */
export interface MatchResult {
  candidate_id: string;
  total_score: number;
  dimension_scores: DimensionScores;
  strengths: string[];
  risks: string[];
  evidence?: Evidence[];
  recommendation: string;
  summary?: string;
}

export interface Evidence {
  claim?: string;
  source?: string;
  text: string;
  score?: number;
  metadata?: Record<string, any>;
}

/** Evidence ReAct Agent 的工具调用审计记录。 */
export interface AgentToolCallTrace {
  call_id: string;
  iteration: number;
  tool_name: string;
  arguments: Record<string, any>;
  status: "success" | "empty" | "correctable_error" | "failed" | "blocked";
  attempts: number;
  duration_ms: number;
  result_count: number;
  observation_summary: string;
  error_category?: "transient" | "invalid_input" | "permanent" | "security" | "unknown" | null;
  error_message?: string | null;
}

/** Evidence Agent 的结构化错误。 */
export interface EvidenceAgentError {
  code: string;
  category: "transient" | "invalid_input" | "permanent" | "security" | "unknown";
  message: string;
  retryable: boolean;
  tool_name?: string | null;
  attempts: number;
}

/** 单个候选人的受控 ReAct 运行结果。 */
export interface EvidenceAgentRun {
  candidate_id: string;
  status: "completed" | "insufficient_evidence" | "needs_human_review";
  iterations: number;
  model_retry_count: number;
  tool_call_count: number;
  tool_calls: AgentToolCallTrace[];
  evidence: Evidence[];
  coverage_rate: number;
  covered_dimensions: string[];
  missing_dimensions: string[];
  reason_summary: string;
  stop_reason: string;
  requires_human_review: boolean;
  errors: EvidenceAgentError[];
}

/** 工具重试耗尽后，后端提供给用户的处理选项。 */
export interface EvidenceIntervention {
  candidate_id: string;
  title: string;
  message: string;
  error_code: string;
  available_actions: AgentInterventionAction[];
}

/** 用户可以对失败的 Evidence Agent 执行的操作。 */
export type AgentInterventionAction =
  | "retry_agent"
  | "continue_with_warning"
  | "skip_failed"
  | "abort";

/** LangGraph 可以停在证据审核或最终排名审核，也可以正常完成或失败。 */
export type WorkflowStatus =
  | "evidence_agent_needs_review"
  | "pending_review"
  | "completed"
  | "failed"
  | "not_found";

/** 恢复 LangGraph 时允许提交的全部人工动作。 */
export type WorkflowResumeAction =
  | AgentInterventionAction
  | "approve_shortlist"
  | "reject"
  | "modify";

/** LangGraph 启动、恢复和状态查询共用的响应结构。 */
export interface WorkflowResponse {
  status: WorkflowStatus;
  message: string;
  thread_id: string;
  job_id?: string;
  limit?: number;
  total_in_db?: number;
  prescreened?: number;
  llm_scored?: number;
  ranking?: {
    ranked_candidates?: RankedCandidate[];
    shortlist?: string[];
  };
  match_results?: MatchResult[];
  agent_runs?: EvidenceAgentRun[];
  interventions?: EvidenceIntervention[];
  selected_candidate_ids?: string[];
  human_review_status?: string;
  errors?: string[];
  next_steps?: string[];
}

/** 排序结果 */
export interface RankingResult {
  job_id: string;
  ranked_candidates: RankedCandidate[];
}

export interface RankedCandidate {
  rank: number;
  candidate_id: string;
  total_score: number;
  dimension_scores: DimensionScores;
  strengths: string[];
  risks: string[];
  recommendation: string;
  summary?: string;
}

/** 匹配详情响应 */
export interface MatchDetail {
  total_score: number;
  dimension_scores: DimensionScores;
  evidence: Evidence[];
  strengths: string[];
  risks: string[];
  recommendation: string;
  summary?: string;
}

/** 面试问题 */
export interface InterviewQuestion {
  question_id: string;
  question_type: "technical" | "project_deep_dive" | "behavioral" | "risk_verification" | string;
  question: string;
  purpose: string;
}

/** 面试评价 */
export interface InterviewEvaluation {
  technical_depth_score?: number;
  communication_score?: number;
  problem_solving_score?: number;
  risk_resolution?: Array<{
    risk: string;
    status: "resolved" | "partially_resolved" | "unresolved" | string;
    reason: string;
  }>;
  strengths: string[];
  concerns: string[];
  summary: string;
  recommendation: "Strongly Recommend" | "Recommend" | "Hold" | "Not Recommend" | string;
  requires_human_review: boolean;
}

/** 邮件草稿 */
export interface EmailDraft {
  email_id: string;
  email_type: "interview_invite" | "rejection" | "follow_up" | "next_round" | string;
  subject: string;
  body: string;
  status: "draft" | "approved" | string;
  requires_human_approval?: boolean;
}

/** API 统一响应包装 */
export interface ApiResponse<T> {
  data?: T;
  loading: boolean;
  error: string | null;
}
