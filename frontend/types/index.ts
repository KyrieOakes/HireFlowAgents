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
  claim: string;
  source: string;
  text: string;
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

/** API 统一响应包装 */
export interface ApiResponse<T> {
  data?: T;
  loading: boolean;
  error: string | null;
}
