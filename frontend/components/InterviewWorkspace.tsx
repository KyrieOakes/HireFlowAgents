// ================================================================
// 单候选人面试工作台
// 负责加载并隔离一个 jobId + candidateId 下的面试题、评价和邮件草稿。
// ================================================================

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type {
  Candidate,
  EmailDraft,
  InterviewEvaluation,
  InterviewQuestion,
  Job,
  MatchDetail,
} from "@/types";
import {
  approveEmailDraft,
  createEmailDraft,
  generateInterviewQuestions,
  getCandidate,
  getEmailDrafts,
  getInterviewEvaluation,
  getInterviewQuestions,
  getJob,
  getMatchDetail,
  submitInterviewEvaluation,
} from "@/services/api";
import ErrorMessage from "@/components/ErrorMessage";
import LoadingButton from "@/components/LoadingButton";
import Modal from "@/components/Modal";
import ScoreBar from "@/components/ScoreBar";
import StatusBadge from "@/components/StatusBadge";


/** 邮件类型使用固定联合类型，防止把任意字符串提交给后端。 */
type EmailType = "interview_invite" | "rejection" | "follow_up" | "next_round";


interface Props {
  /** 当前岗位 ID。 */
  jobId: string;
  /** 当前候选人 ID。 */
  candidateId: string;
  /** 返回名单页时需要恢复的 LangGraph checkpoint。 */
  returnThreadId?: string;
}


/**
 * 展示单个候选人的完整面试生命周期。
 * 路由参数变化时会先清空旧状态，再重新从数据库加载，避免显示上一位候选人的内容。
 */
export default function InterviewWorkspace({ jobId, candidateId, returnThreadId = "" }: Props) {
  const [job, setJob] = useState<Job | null>(null);
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [detail, setDetail] = useState<MatchDetail | null>(null);
  const [questions, setQuestions] = useState<InterviewQuestion[]>([]);
  const [evaluation, setEvaluation] = useState<InterviewEvaluation | null>(null);
  const [drafts, setDrafts] = useState<EmailDraft[]>([]);
  const [feedback, setFeedback] = useState("");
  const [emailType, setEmailType] = useState<EmailType>("interview_invite");
  const [pageLoading, setPageLoading] = useState(true);
  const [stageLoading, setStageLoading] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [scoreModalOpen, setScoreModalOpen] = useState(false);
  // React state 更新不是同步锁，因此额外用 Set 防止用户快速双击造成重复的大模型调用。
  const actionLocksRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;

    /** 从后端恢复当前候选人已经保存的全部面试数据。 */
    async function loadWorkspace() {
      setPageLoading(true);
      setError(null);
      // 路由切换后立即清空旧候选人的信息，不能等新请求返回后再覆盖。
      setJob(null);
      setCandidate(null);
      setDetail(null);
      setQuestions([]);
      setEvaluation(null);
      setDrafts([]);
      setFeedback("");
      setScoreModalOpen(false);

      try {
        // 基础信息、匹配详情、历史问题和邮件互不依赖，可以并发读取以缩短等待时间。
        const [jobData, candidateData, matchData, questionData, draftData] = await Promise.all([
          getJob(jobId),
          getCandidate(candidateId),
          getMatchDetail(jobId, candidateId),
          getInterviewQuestions(jobId, candidateId),
          getEmailDrafts(jobId, candidateId),
        ]);
        if (cancelled) return;

        setJob(jobData);
        setCandidate(candidateData);
        setDetail(matchData);
        setQuestions(questionData.questions);
        setDrafts(draftData.drafts);

        // “尚无评价”是新候选人的正常状态，因此不能让 404 阻断整个工作台。
        try {
          const evaluationData = await getInterviewEvaluation(jobId, candidateId);
          if (!cancelled) {
            setEvaluation(evaluationData.evaluation);
            setFeedback(evaluationData.feedback_text || "");
          }
        } catch (evaluationError: any) {
          const message = evaluationError?.message || "";
          if (!message.includes("还没有面试评价") && !cancelled) {
            setError(`面试评价读取失败：${message}`);
          }
        }
      } catch (loadError: any) {
        if (!cancelled) setError(loadError?.message || "面试工作台加载失败");
      } finally {
        if (!cancelled) setPageLoading(false);
      }
    }

    void loadWorkspace();
    return () => {
      cancelled = true;
    };
  }, [jobId, candidateId]);

  /** 给单个异步操作添加按钮加载状态、错误处理和同步防重复锁。 */
  async function withStageLoading(key: string, action: () => Promise<void>) {
    if (actionLocksRef.current.has(key)) return;
    actionLocksRef.current.add(key);
    setStageLoading((current) => ({ ...current, [key]: true }));
    setError(null);
    try {
      await action();
    } catch (actionError: any) {
      setError(actionError?.message || "操作失败，请稍后重试");
    } finally {
      actionLocksRef.current.delete(key);
      setStageLoading((current) => ({ ...current, [key]: false }));
    }
  }

  /** 调用 Interview Agent，并用后端返回结果替换当前问题列表。 */
  async function handleGenerateQuestions() {
    await withStageLoading("questions", async () => {
      const response = await generateInterviewQuestions(jobId, candidateId);
      setQuestions(response.questions);
    });
  }

  /** 提交 HR 的真实面试记录，再显示 Evaluation Agent 的结构化评价。 */
  async function handleSubmitEvaluation() {
    const cleanFeedback = feedback.trim();
    if (!cleanFeedback) return;
    await withStageLoading("evaluation", async () => {
      const response = await submitInterviewEvaluation(jobId, candidateId, cleanFeedback);
      setEvaluation(response.evaluation);
    });
  }

  /** 创建草稿后重新读取列表，保证新草稿和历史草稿使用同一数据源。 */
  async function handleCreateDraft() {
    await withStageLoading("draft", async () => {
      await createEmailDraft(jobId, candidateId, emailType);
      const response = await getEmailDrafts(jobId, candidateId);
      setDrafts(response.drafts);
    });
  }

  /** 人工批准只改变草稿状态，不会真正发送邮件。 */
  async function handleApproveDraft(emailId: string) {
    await withStageLoading(`approve-${emailId}`, async () => {
      await approveEmailDraft(emailId);
      const response = await getEmailDrafts(jobId, candidateId);
      setDrafts(response.drafts);
    });
  }

  // 返回链接携带明确的 checkpoint；名单页只在这种场景下自动恢复当前结果。
  const returnHref = returnThreadId
    ? {
        pathname: "/matching",
        query: { returnJobId: jobId, returnThreadId },
      }
    : "/matching";

  if (pageLoading) {
    return (
      <div className="glass-pad flex min-h-64 items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-slate-900" />
          <p className="mt-3 text-sm text-slate-500">正在加载候选人面试工作台...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 soft-enter">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          href={returnHref}
          className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 transition hover:text-slate-950"
        >
          <span aria-hidden="true">←</span>
          返回面试名单
        </Link>
        <span className="text-xs text-slate-400">面试内容按岗位和候选人独立保存</span>
      </div>

      {error && <ErrorMessage message={error} />}

      {/* 候选人摘要固定处于工作台顶部，让后续每一步都有明确上下文。 */}
      <section className="glass-pad">
        <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-start">
          <div className="min-w-0">
            <p className="section-label">Interview Workspace</p>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <h1 className="page-title">{candidate?.name || candidateId}</h1>
              {detail && <StatusBadge level={detail.recommendation} />}
            </div>
            <p className="mt-2 text-sm text-slate-500">
              岗位：{job?.title || jobId}
              <span className="mx-2 text-slate-300">·</span>
              候选人 ID：{candidateId}
            </p>
            {candidate?.profile?.skills && candidate.profile.skills.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {candidate.profile.skills.slice(0, 8).map((skill) => (
                  <span key={skill} className="chip-blue">{skill}</span>
                ))}
              </div>
            )}
          </div>

          <div className="flex shrink-0 items-center gap-4 rounded-lg border border-slate-200 bg-white/70 px-4 py-3">
            <div>
              <p className="text-xs text-slate-400">匹配总分</p>
              <p className="mt-1 text-2xl font-semibold text-slate-950">
                {detail?.total_score ?? "--"}
                <span className="text-sm font-normal text-slate-400">/100</span>
              </p>
            </div>
            <button
              type="button"
              onClick={() => setScoreModalOpen(true)}
              disabled={!detail}
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-300 hover:text-slate-950 disabled:cursor-not-allowed disabled:opacity-50"
            >
              查看详细评分
            </button>
          </div>
        </div>

        {detail && (
          <div className="mt-5 grid gap-3 md:grid-cols-2">
            <SummaryList title="匹配优势" items={detail.strengths} tone="positive" />
            <SummaryList title="面试关注风险" items={detail.risks} tone="negative" />
          </div>
        )}
      </section>

      {/* 步骤条只表达业务顺序，不强制 HR 完成前一步才能查看后一步。 */}
      <ol className="grid gap-3 sm:grid-cols-3">
        <WorkspaceStep number="1" title="准备面试题" description="技术、项目与风险验证" active />
        <WorkspaceStep number="2" title="记录并评价" description="人工反馈 + Agent 评价" active={Boolean(evaluation)} />
        <WorkspaceStep number="3" title="邮件跟进" description="生成草稿并人工批准" active={drafts.length > 0} />
      </ol>

      <section id="interview-questions" className="glass-pad scroll-mt-24">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="section-label">Step 1</p>
            <h2 className="mt-2 text-lg font-semibold text-slate-950">面试问题</h2>
            <p className="mt-1 text-sm text-slate-500">Interview Agent 会结合岗位要求、匹配优势和风险点生成针对性问题。</p>
          </div>
          <LoadingButton
            onClick={handleGenerateQuestions}
            loading={Boolean(stageLoading.questions)}
            variant={questions.length > 0 ? "secondary" : "primary"}
          >
            {questions.length > 0 ? "重新生成面试题" : "生成面试题"}
          </LoadingButton>
        </div>

        {questions.length > 0 ? (
          <div className="mt-5 grid gap-3 lg:grid-cols-2">
            {questions.map((question, index) => (
              <article key={question.question_id || question.question} className="rounded-lg border border-slate-200 bg-white/80 p-4">
                <div className="flex items-center justify-between gap-3">
                  <span className="chip-blue">{questionTypeLabel(question.question_type)}</span>
                  <span className="text-xs font-medium text-slate-400">Q{index + 1}</span>
                </div>
                <p className="mt-3 text-sm font-semibold leading-6 text-slate-900">{question.question}</p>
                <div className="mt-3 rounded-md bg-slate-50 p-3">
                  <p className="text-xs font-semibold text-slate-500">考察目的</p>
                  <p className="mt-1 text-xs leading-5 text-slate-600">{question.purpose}</p>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <WorkspaceEmpty
            title="还没有面试问题"
            description="点击“生成面试题”后，问题会保存在当前岗位与候选人名下。"
          />
        )}
      </section>

      <section id="interview-evaluation" className="glass-pad scroll-mt-24">
        <div>
          <p className="section-label">Step 2</p>
          <h2 className="mt-2 text-lg font-semibold text-slate-950">面试记录与评价</h2>
          <p className="mt-1 text-sm text-slate-500">由面试官提供真实记录，Evaluation Agent 只负责整理和辅助判断。</p>
        </div>

        <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)]">
          <div>
            <label className="text-sm font-semibold text-slate-800" htmlFor="interview-feedback">面试官反馈</label>
            <textarea
              id="interview-feedback"
              value={feedback}
              onChange={(event) => setFeedback(event.target.value)}
              rows={9}
              className="field mt-2 resize-y"
              placeholder="填写技术回答、项目追问、沟通表现，以及风险点是否得到澄清..."
            />
            <div className="mt-3 flex items-center justify-between gap-3">
              <span className="text-xs text-slate-400">评价结果仍需 HR 人工审核，不会自动做录用决定。</span>
              <LoadingButton
                onClick={handleSubmitEvaluation}
                loading={Boolean(stageLoading.evaluation)}
                disabled={!feedback.trim()}
              >
                {evaluation ? "重新生成评价" : "生成结构化评价"}
              </LoadingButton>
            </div>
          </div>

          {evaluation ? (
            <div className="rounded-lg border border-slate-200 bg-white/80 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs text-slate-400">Agent 建议</p>
                  <p className="mt-1 font-semibold text-slate-950">{evaluation.recommendation}</p>
                </div>
                {evaluation.requires_human_review && <span className="chip">需人工审核</span>}
              </div>
              <p className="mt-4 text-sm leading-6 text-slate-600">{evaluation.summary}</p>
              <div className="mt-4 grid grid-cols-3 gap-2">
                <EvaluationScore label="技术深度" score={evaluation.technical_depth_score} />
                <EvaluationScore label="沟通表达" score={evaluation.communication_score} />
                <EvaluationScore label="问题解决" score={evaluation.problem_solving_score} />
              </div>
              {evaluation.concerns?.length > 0 && (
                <div className="mt-4 rounded-md bg-rose-50 p-3">
                  <p className="text-xs font-semibold text-rose-700">仍需关注</p>
                  <ul className="mt-2 space-y-1 text-xs leading-5 text-slate-600">
                    {evaluation.concerns.map((concern) => <li key={concern}>• {concern}</li>)}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <WorkspaceEmpty title="尚未生成评价" description="填写左侧面试反馈后，再交给 Agent 生成结构化评价。" compact />
          )}
        </div>
      </section>

      <section id="email-follow-up" className="glass-pad scroll-mt-24">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="section-label">Step 3</p>
            <h2 className="mt-2 text-lg font-semibold text-slate-950">HR 邮件跟进</h2>
            <p className="mt-1 text-sm text-slate-500">系统只生成草稿；批准草稿也不会自动发送邮件。</p>
          </div>
          <div className="flex w-full gap-2 sm:w-auto">
            <select
              value={emailType}
              onChange={(event) => setEmailType(event.target.value as EmailType)}
              className="field min-w-40"
            >
              <option value="interview_invite">面试邀请</option>
              <option value="next_round">下一轮通知</option>
              <option value="follow_up">跟进邮件</option>
              <option value="rejection">拒信</option>
            </select>
            <LoadingButton onClick={handleCreateDraft} loading={Boolean(stageLoading.draft)}>
              生成草稿
            </LoadingButton>
          </div>
        </div>

        {drafts.length > 0 ? (
          <div className="mt-5 space-y-3">
            {drafts.map((draft) => (
              <article key={draft.email_id} className="rounded-lg border border-slate-200 bg-white/80 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs text-slate-400">邮件主题</p>
                    <h3 className="mt-1 text-sm font-semibold text-slate-950">{draft.subject}</h3>
                  </div>
                  <span className={draft.status === "approved" ? "chip-green" : "chip"}>
                    {draft.status === "approved" ? "已批准（未发送）" : "待人工批准"}
                  </span>
                </div>
                <pre className="mt-4 max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 p-4 font-sans text-sm leading-6 text-slate-600">
                  {draft.body}
                </pre>
                {draft.status !== "approved" && (
                  <div className="mt-3 text-right">
                    <LoadingButton
                      onClick={() => handleApproveDraft(draft.email_id)}
                      loading={Boolean(stageLoading[`approve-${draft.email_id}`])}
                      variant="secondary"
                    >
                      人工批准草稿
                    </LoadingButton>
                  </div>
                )}
              </article>
            ))}
          </div>
        ) : (
          <WorkspaceEmpty title="还没有邮件草稿" description="选择邮件类型后生成草稿，再由 HR 审核内容。" />
        )}
      </section>

      <Modal
        open={scoreModalOpen && Boolean(detail)}
        onClose={() => setScoreModalOpen(false)}
        title={`详细评分 · ${candidate?.name || candidateId}`}
        maxWidthClass="max-w-2xl"
      >
        {detail && <MatchDetailContent detail={detail} />}
      </Modal>
    </div>
  );
}


/** 工作台顶部的优势或风险摘要。 */
function SummaryList({
  title,
  items,
  tone,
}: {
  title: string;
  items: string[];
  tone: "positive" | "negative";
}) {
  const toneClass = tone === "positive"
    ? "border-emerald-100 bg-emerald-50/70 text-emerald-700"
    : "border-rose-100 bg-rose-50/70 text-rose-700";
  return (
    <div className={`rounded-lg border p-4 ${toneClass}`}>
      <p className="text-xs font-semibold">{title}</p>
      {items?.length > 0 ? (
        <ul className="mt-2 space-y-1 text-xs leading-5 text-slate-600">
          {items.slice(0, 3).map((item) => <li key={item}>• {item}</li>)}
        </ul>
      ) : (
        <p className="mt-2 text-xs text-slate-400">暂无</p>
      )}
    </div>
  );
}


/** 三步业务流程的轻量步骤提示。 */
function WorkspaceStep({
  number,
  title,
  description,
  active,
}: {
  number: string;
  title: string;
  description: string;
  active: boolean;
}) {
  return (
    <li className={`rounded-lg border p-4 ${active ? "border-sky-200 bg-white" : "border-slate-200 bg-white/60"}`}>
      <div className="flex items-center gap-3">
        <span className={`flex h-8 w-8 items-center justify-center rounded-md text-sm font-semibold ${active ? "bg-slate-950 text-white" : "bg-slate-100 text-slate-400"}`}>
          {number}
        </span>
        <div>
          <p className="text-sm font-semibold text-slate-900">{title}</p>
          <p className="mt-0.5 text-xs text-slate-500">{description}</p>
        </div>
      </div>
    </li>
  );
}


/** 工作台内统一的空状态，避免用大块空白代替业务提示。 */
function WorkspaceEmpty({
  title,
  description,
  compact = false,
}: {
  title: string;
  description: string;
  compact?: boolean;
}) {
  return (
    <div className={`rounded-lg border border-dashed border-slate-300 bg-slate-50/70 text-center ${compact ? "flex min-h-56 flex-col justify-center p-5" : "mt-5 p-8"}`}>
      <p className="text-sm font-semibold text-slate-700">{title}</p>
      <p className="mt-1 text-xs leading-5 text-slate-500">{description}</p>
    </div>
  );
}


/** 评价分数字段可能为空；为空时明确展示占位符而不是伪造 0 分。 */
function EvaluationScore({ label, score }: { label: string; score?: number }) {
  return (
    <div className="rounded-md bg-slate-50 p-3 text-center">
      <p className="text-lg font-semibold text-slate-900">{score ?? "--"}</p>
      <p className="mt-1 text-[11px] text-slate-500">{label}</p>
    </div>
  );
}


/** 复用名单页的详细评分信息结构，但弹窗属于当前候选人工作台。 */
function MatchDetailContent({ detail }: { detail: MatchDetail }) {
  return (
    <div className="space-y-5 p-5">
      <div className="flex items-center gap-3">
        <span className="text-3xl font-semibold tracking-tight text-slate-950">{detail.total_score}</span>
        <span className="text-sm text-slate-400">/ 100</span>
        <StatusBadge level={detail.recommendation} />
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-slate-700">维度得分</h3>
        <div className="space-y-2">
          {detail.dimension_scores && Object.entries(detail.dimension_scores).map(([key, value]) => (
            <ScoreBar key={key} label={dimensionLabel(key)} score={value} maxScore={30} />
          ))}
        </div>
      </div>

      {detail.evidence?.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-slate-700">支撑证据</h3>
          <div className="space-y-2">
            {detail.evidence.map((evidence, index) => (
              <div key={`${evidence.text}-${index}`} className="rounded-md bg-slate-50 p-3 text-xs">
                <p className="font-semibold text-slate-700">{evidence.claim || `证据 ${index + 1}`}</p>
                <p className="mt-1 leading-5 text-slate-600">{evidence.text}</p>
                <p className="mt-1 text-slate-400">来源：{evidence.source || evidence.metadata?.source || "简历片段"}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {detail.summary && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-700">匹配总结</h3>
          <p className="text-sm leading-6 text-slate-600">{detail.summary}</p>
        </div>
      )}
    </div>
  );
}


/** 把后端稳定的面试问题类型转换为中文标签。 */
function questionTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    technical: "技术",
    project_deep_dive: "项目深挖",
    behavioral: "行为",
    risk_verification: "风险验证",
  };
  return labels[type] || type;
}


/** 把评分字段转换为页面展示名称。 */
function dimensionLabel(key: string): string {
  const labels: Record<string, string> = {
    technical_skills: "技术技能",
    project_relevance: "项目相关性",
    experience: "工作经验",
    education: "教育背景",
    domain_relevance: "领域相关性",
    communication: "沟通表达",
    risk_penalty: "风险扣分",
  };
  return labels[key] || key;
}
