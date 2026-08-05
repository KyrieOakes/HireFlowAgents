// ================================================================
// 匹配排名页 — 选择岗位 → 触发匹配 → 展示排名 + 详情
// ================================================================

import { useEffect, useState, useRef } from "react";
import type {
  AgentInterventionAction,
  Candidate,
  EmailDraft,
  EvidenceAgentRun,
  EvidenceIntervention,
  InterviewEvaluation,
  InterviewQuestion,
  Job,
  MatchDetail,
  RankedCandidate,
  WorkflowResponse,
  WorkflowStatus,
} from "@/types";
import {
  listJobs,
  listCandidates,
  startMatchingWorkflow,
  resumeMatchingWorkflow,
  getMatchingWorkflowState,
  getMatchDetail,
  generateInterviewQuestions,
  submitInterviewEvaluation,
  createEmailDraft,
  getEmailDrafts,
  approveEmailDraft,
} from "@/services/api";
import LoadingButton from "@/components/LoadingButton";
import ErrorMessage from "@/components/ErrorMessage";
import EmptyState from "@/components/EmptyState";
import StatusBadge from "@/components/StatusBadge";
import ScoreBar from "@/components/ScoreBar";
import AgentTracePanel from "@/components/AgentTracePanel";
import Modal from "@/components/Modal";

export default function MatchingPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string>("");
  const [limit, setLimit] = useState<number>(5);  // 匹配人数限制, 默认Top5
  const [matching, setMatching] = useState(false);
  const matchLock = useRef(false);        // 匹配防抖锁
  const detailLock = useRef<Set<string>>(new Set()); // 详情防抖锁
  const [ranked, setRanked] = useState<RankedCandidate[]>([]);
  const [detail, setDetail] = useState<MatchDetail | null>(null);
  const [detailId, setDetailId] = useState<string>("");
  const [detailLoading, setDetailLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);  // 匹配耗时计时器
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const [selectedCandidateId, setSelectedCandidateId] = useState("");
  const [questions, setQuestions] = useState<InterviewQuestion[]>([]);
  const [evaluation, setEvaluation] = useState<InterviewEvaluation | null>(null);
  const [drafts, setDrafts] = useState<EmailDraft[]>([]);
  const [feedback, setFeedback] = useState("");
  const [emailType, setEmailType] = useState<"interview_invite" | "rejection" | "follow_up" | "next_round">("interview_invite");
  const [stageLoading, setStageLoading] = useState<Record<string, boolean>>({});
  // Evidence Agent 的执行轨迹与人工介入状态会直接显示在匹配结果上方。
  const [agentRuns, setAgentRuns] = useState<EvidenceAgentRun[]>([]);
  const [agentInterventions, setAgentInterventions] = useState<EvidenceIntervention[]>([]);
  const [agentMessage, setAgentMessage] = useState("");
  // LangGraph thread_id 是 PostgreSQL checkpoint 的恢复钥匙，页面刷新后也会复用。
  const [workflowThreadId, setWorkflowThreadId] = useState("");
  const [workflowStatus, setWorkflowStatus] = useState<WorkflowStatus | "">("");
  // 最终人工审核允许 HR 勾选真正进入面试的候选人。
  const [reviewCandidateIds, setReviewCandidateIds] = useState<string[]>([]);
  const [defaultShortlistIds, setDefaultShortlistIds] = useState<string[]>([]);

  // candidate_id → name 映射表 (用于显示姓名而非ID)
  const nameMap: Record<string, string> = {};
  candidates.forEach((c) => { nameMap[c.candidate_id] = c.name || c.candidate_id; });

  // 人工审核前展示完整排名，方便 HR 对比和勾选；审核完成后只展示最终入选名单。
  const visibleRanked = workflowStatus === "completed"
    ? ranked.filter((candidate) => reviewCandidateIds.includes(candidate.candidate_id))
    : ranked;

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const [jobList, candidateList] = await Promise.all([listJobs(), listCandidates()]);
        setJobs(jobList);
        setCandidates(candidateList);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // 用户切换岗位时，尝试从浏览器保存的 thread_id 恢复 PostgreSQL checkpoint。
  useEffect(() => {
    if (!selectedJobId) return;
    const savedThreadId = window.localStorage.getItem(`hireflow-workflow:${selectedJobId}`);
    if (!savedThreadId) return;

    let cancelled = false;
    (async () => {
      setMatching(true);
      try {
        const response = await getMatchingWorkflowState(savedThreadId);
        if (cancelled) return;
        if (response.status === "not_found") {
          window.localStorage.removeItem(`hireflow-workflow:${selectedJobId}`);
          return;
        }
        applyWorkflowResponse(response);
      } catch {
        // 恢复失败不阻止用户重新点击“开始匹配”；后端错误会在新运行时正常显示。
      } finally {
        if (!cancelled) setMatching(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [selectedJobId]);

  /** 把启动、恢复、状态查询的统一响应同步到页面。 */
  function applyWorkflowResponse(response: WorkflowResponse) {
    setWorkflowThreadId(response.thread_id || "");
    setWorkflowStatus(response.status);
    setAgentRuns(response.agent_runs || []);
    setAgentInterventions(response.interventions || []);
    setAgentMessage(response.message || "");

    const ranking = response.ranking;
    if (ranking?.ranked_candidates) {
      setRanked(ranking.ranked_candidates);
      const shortlist = ranking.shortlist || [];
      setDefaultShortlistIds(shortlist);
      setReviewCandidateIds(
        response.selected_candidate_ids?.length
          ? response.selected_candidate_ids
          : shortlist,
      );
      setSelectedCandidateId(
        response.selected_candidate_ids?.[0]
          || ranking.ranked_candidates[0]?.candidate_id
          || "",
      );
    }

    if (response.errors?.length) {
      setError(response.errors.join("；"));
    }
  }

  /** 开始一次耗时的 LangGraph 请求，并启动页面计时器。 */
  function beginWorkflowRequest() {
    matchLock.current = true;
    setMatching(true);
    setError(null);
    setElapsed(0);
    timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
  }

  /** 结束 LangGraph 请求，释放防重复点击锁。 */
  function finishWorkflowRequest() {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    matchLock.current = false;
    setMatching(false);
  }

  // 执行匹配：现在正式从 /workflow/run 进入 LangGraph，而不是直连 /jobs/{id}/match。
  async function handleMatch() {
    if (!selectedJobId || matchLock.current) return;
    beginWorkflowRequest();
    setRanked([]);
    setAgentRuns([]);
    setAgentInterventions([]);
    setWorkflowStatus("");
    setWorkflowThreadId("");
    setReviewCandidateIds([]);
    setDefaultShortlistIds([]);
    try {
      const response = await startMatchingWorkflow(selectedJobId, limit);
      applyWorkflowResponse(response);
      // 保存 thread_id 后，即使刷新页面也可以通过 GET /workflow/{id}/state 恢复。
      window.localStorage.setItem(`hireflow-workflow:${selectedJobId}`, response.thread_id);
      setQuestions([]);
      setEvaluation(null);
      setDrafts([]);
      setFeedback("");
    } catch (e: any) {
      setError(e.message);
    } finally {
      finishWorkflowRequest();
    }
  }

  /** 从当前 interrupt 恢复工作流；证据处理和最终排名审核都复用此函数。 */
  async function continueWorkflow(
    action: AgentInterventionAction | "approve_shortlist" | "reject" | "modify",
    selectedIds: string[] = [],
  ) {
    if (!workflowThreadId || matchLock.current) return;
    beginWorkflowRequest();
    try {
      const response = await resumeMatchingWorkflow(workflowThreadId, action, selectedIds);
      applyWorkflowResponse(response);
    } catch (e: any) {
      setError(e.message);
    } finally {
      finishWorkflowRequest();
    }
  }

  /** Evidence Agent 失败后，把按钮选择交给同一个 LangGraph checkpoint。 */
  async function handleAgentResolution(action: AgentInterventionAction) {
    await continueWorkflow(action);
  }

  /** 人工确认默认 shortlist；手动改动过名单时使用 modify 动作。 */
  async function handleApproveRanking() {
    const current = [...reviewCandidateIds].sort().join(",");
    const original = [...defaultShortlistIds].sort().join(",");
    await continueWorkflow(
      current === original ? "approve_shortlist" : "modify",
      reviewCandidateIds,
    );
  }

  /** 勾选或取消一名候选人进入最终面试名单。 */
  function toggleReviewCandidate(candidateId: string) {
    setReviewCandidateIds((current) =>
      current.includes(candidateId)
        ? current.filter((id) => id !== candidateId)
        : [...current, candidateId],
    );
  }

  async function withStageLoading(key: string, action: () => Promise<void>) {
    setStageLoading((prev) => ({ ...prev, [key]: true }));
    setError(null);
    try {
      await action();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setStageLoading((prev) => ({ ...prev, [key]: false }));
    }
  }

  async function handleGenerateQuestions() {
    if (!selectedJobId || !selectedCandidateId) return;
    await withStageLoading("questions", async () => {
      const res = await generateInterviewQuestions(selectedJobId, selectedCandidateId);
      setQuestions(res.questions);
    });
  }

  async function handleSubmitEvaluation() {
    if (!selectedJobId || !selectedCandidateId || !feedback.trim()) return;
    await withStageLoading("evaluation", async () => {
      const res = await submitInterviewEvaluation(selectedJobId, selectedCandidateId, feedback.trim());
      setEvaluation(res.evaluation);
    });
  }

  async function handleCreateDraft() {
    if (!selectedJobId || !selectedCandidateId) return;
    await withStageLoading("draft", async () => {
      await createEmailDraft(selectedJobId, selectedCandidateId, emailType);
      const res = await getEmailDrafts(selectedJobId, selectedCandidateId);
      setDrafts(res.drafts);
    });
  }

  async function handleApproveDraft(emailId: string) {
    if (!selectedJobId || !selectedCandidateId) return;
    await withStageLoading(`approve-${emailId}`, async () => {
      await approveEmailDraft(emailId);
      const res = await getEmailDrafts(selectedJobId, selectedCandidateId);
      setDrafts(res.drafts);
    });
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
    <div className="space-y-6 soft-enter">
      <div className="glass-pad">
        <p className="section-label">Matching Pipeline</p>
        <h1 className="page-title mt-2">匹配与面试</h1>
        <p className="page-subtitle">
          先完成候选人排序，再基于风险点生成面试问题、结构化评价和 HR 邮件草稿。
        </p>
      </div>

      {error && <div className="mb-4"><ErrorMessage message={error} /></div>}

      {/* ---- 选择岗位 + 触发匹配 ---- */}
      <div className="glass-pad">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-slate-900">执行匹配</h2>
            <p className="mt-1 text-sm text-slate-500">粗筛后先运行 Evidence ReAct Agent，再调用 Match Agent 和 Ranking Agent。</p>
          </div>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[200px]">
            <label className="mb-1 block text-xs font-medium text-slate-500">选择岗位</label>
            <select
              value={selectedJobId}
              onChange={(e) => setSelectedJobId(e.target.value)}
              className="field"
            >
              <option value="">— 请选择已解析的岗位 —</option>
              {jobs.filter((j) => (j.has_profile || j.jd_profile)).map((j) => (
                <option key={j.job_id} value={j.job_id}>{j.title || j.job_id}</option>
              ))}
            </select>
          </div>
          <div className="w-32">
            <label className="mb-1 block text-xs font-medium text-slate-500">匹配人数</label>
            <select
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="field"
            >
              <option value={5}>Top 5</option>
              <option value={10}>Top 10</option>
              <option value={15}>Top 15</option>
              <option value={0}>全部</option>
            </select>
          </div>
          <LoadingButton onClick={() => handleMatch()} loading={matching} disabled={!selectedJobId}>
            开始匹配
          </LoadingButton>
        </div>
        {/* 匹配进度提示 */}
        {matching && (
          <div className="mt-4 rounded-lg border border-sky-200 bg-sky-50/80 p-3 backdrop-blur">
            <div className="flex items-center gap-3">
              <svg className="animate-spin h-5 w-5 text-blue-600" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
              <span className="text-sm text-sky-700">
                正在匹配中... Evidence Agent 正在规划查询并调用工具
              </span>
            </div>
            <p className="mt-2 text-xs text-sky-500">已等待 {elapsed} 秒 | 本地模型处理中, 请耐心等候</p>
          </div>
        )}
        {jobs.filter((j) => (j.has_profile || j.jd_profile)).length === 0 && (
          <p className="mt-2 text-xs text-slate-400">还没有已解析的岗位，请先到「岗位」创建并解析 JD。</p>
        )}
      </div>

      {/* ---- ReAct Agent 可审计轨迹 + 人工错误处理 ---- */}
      <AgentTracePanel
        runs={agentRuns}
        interventions={agentInterventions}
        candidateNames={nameMap}
        message={agentMessage}
        loading={matching}
        onResolve={handleAgentResolution}
      />

      {/* ---- LangGraph 最终排名人工审核 ---- */}
      {workflowStatus === "pending_review" && ranked.length > 0 && (
        <section className="glass-pad border-amber-200 bg-amber-50/70">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="section-label text-amber-700">Human-in-the-loop</p>
              <h2 className="mt-2 text-lg font-semibold text-slate-950">确认进入面试的候选人</h2>
              <p className="mt-1 text-sm text-slate-600">
                LangGraph 已在 Ranking Agent 后暂停。请在排名卡片中勾选名单，再由人工确认继续。
              </p>
              <p className="mt-2 text-xs text-slate-500">
                当前选择 {reviewCandidateIds.length} 人 · Thread {workflowThreadId.slice(0, 28)}…
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={matching}
                onClick={() => continueWorkflow("reject")}
                className="rounded-md border border-rose-300 bg-white px-4 py-2 text-sm font-medium text-rose-700 transition hover:bg-rose-50 disabled:opacity-50"
              >
                驳回并重新评分
              </button>
              <button
                type="button"
                disabled={matching || reviewCandidateIds.length === 0}
                onClick={handleApproveRanking}
                className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                确认面试名单
              </button>
            </div>
          </div>
        </section>
      )}

      {workflowStatus === "completed" && ranked.length > 0 && (
        <section className="rounded-lg border border-emerald-200 bg-emerald-50/80 px-4 py-3 text-sm text-emerald-800">
          人工审核已完成，LangGraph 工作流已经结束。现在可以对已确认候选人开展面试跟进。
        </section>
      )}

      {/* ---- 排序结果 ---- */}
      {!matching && visibleRanked.length === 0 && agentInterventions.length === 0 ? (
        <EmptyState title="还没有排名结果" description="选择一个岗位后点击「开始匹配」" />
      ) : (
        <>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="section-label">
              {workflowStatus === "completed" ? "已确认的面试名单" : "排名结果"}
            </h2>
            <span className="text-xs text-slate-400">人工确认后，仅入选候选人可以进入面试跟进</span>
          </div>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
            <div className="space-y-4">
            {visibleRanked.map((c, i) => (
              <div
                key={c.candidate_id}
                className={`focus-card cursor-pointer p-4 ${selectedCandidateId === c.candidate_id ? "border-sky-300 ring-2 ring-sky-100" : ""}`}
                onClick={() => setSelectedCandidateId(c.candidate_id)}
              >
                {/* 头部: 排名 + ID + 分数 + 等级 */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    {/* 排名数字 */}
                    <span className={`flex h-9 w-9 items-center justify-center rounded-md text-sm font-bold text-white ${
                      i === 0 ? "bg-slate-950" : i === 1 ? "bg-slate-600" : i === 2 ? "bg-sky-600" : "bg-slate-300"
                    }`}>
                      {c.rank}
                    </span>
                    <div>
                      <span className="font-semibold text-slate-900">{nameMap[c.candidate_id] || c.candidate_id}</span>
                      <span className="ml-2 text-xs text-slate-400">总分</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {workflowStatus === "pending_review" && (
                      <label
                        className="flex items-center gap-2 text-xs font-medium text-slate-600"
                        onClick={(event) => event.stopPropagation()}
                      >
                        <input
                          type="checkbox"
                          checked={reviewCandidateIds.includes(c.candidate_id)}
                          onChange={() => toggleReviewCandidate(c.candidate_id)}
                          className="h-4 w-4 rounded border-slate-300 text-slate-950"
                        />
                        进入面试
                      </label>
                    )}
                    <span className="text-lg font-bold text-slate-900">{c.total_score}<span className="text-sm font-normal text-slate-400">/100</span></span>
                    <StatusBadge level={c.recommendation} />
                  </div>
                </div>

                {/* 分数条 */}
                <ScoreBar score={c.total_score} />

                {/* 优势 + 风险 */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
                  {/* 优势 */}
                  <div className="rounded-md bg-emerald-50/70 p-3">
                    <div className="mb-1 text-xs font-semibold text-emerald-700">优势</div>
                    {c.strengths?.length > 0 ? (
                      <ul className="space-y-0.5 text-xs text-slate-600">
                        {c.strengths.slice(0, 2).map((s, idx) => (
                          <li key={idx} className="truncate">{s}</li>
                        ))}
                      </ul>
                    ) : <span className="text-xs text-gray-400">暂无</span>}
                  </div>
                  {/* 风险 */}
                  <div className="rounded-md bg-rose-50/70 p-3">
                    <div className="mb-1 text-xs font-semibold text-rose-700">风险</div>
                    {c.risks?.length > 0 ? (
                      <ul className="space-y-0.5 text-xs text-slate-600">
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
            {workflowStatus === "completed" && reviewCandidateIds.includes(selectedCandidateId) ? (
              <InterviewPanel
                candidateId={selectedCandidateId}
                candidateName={nameMap[selectedCandidateId] || selectedCandidateId}
                questions={questions}
                evaluation={evaluation}
                drafts={drafts}
                feedback={feedback}
                emailType={emailType}
                loading={stageLoading}
                onFeedbackChange={setFeedback}
                onEmailTypeChange={setEmailType}
                onGenerateQuestions={handleGenerateQuestions}
                onSubmitEvaluation={handleSubmitEvaluation}
                onCreateDraft={handleCreateDraft}
                onApproveDraft={handleApproveDraft}
              />
            ) : (
              <aside className="focus-card h-fit p-5 text-sm text-slate-500">
                <p className="font-semibold text-slate-900">面试流程尚未解锁</p>
                <p className="mt-2 leading-6">
                  {workflowStatus === "completed"
                    ? "当前候选人不在人工确认的面试名单中，请选择一名已入选候选人。"
                    : "请先完成人工排名审核。系统不会在 HR 确认前自动推进招聘决定。"}
                </p>
              </aside>
            )}
          </div>
        </>
      )}

      {/* Portal 会让弹窗脱离 soft-enter 的 transform 定位上下文。 */}
      <Modal
        open={Boolean(detail)}
        onClose={() => setDetail(null)}
        title={`详细评分${detailId ? ` · ${nameMap[detailId] || detailId}` : ""}`}
        maxWidthClass="max-w-xl"
      >
        {detail && (
            <div className="p-4 space-y-4">
              {/* 总分 + 等级 */}
              <div className="flex items-center gap-3">
                <span className="text-3xl font-semibold tracking-tight text-slate-950">{detail.total_score}</span>
                <span className="text-sm text-slate-400">/ 100</span>
                <StatusBadge level={detail.recommendation} />
              </div>

              {/* 各维度分数 */}
              <div>
                <h4 className="mb-2 text-sm font-semibold text-slate-700">维度得分</h4>
                <div className="space-y-1.5">
                  {detail.dimension_scores && Object.entries(detail.dimension_scores).map(([key, val]) => (
                    <ScoreBar key={key} label={dimLabel(key)} score={val} maxScore={30} />
                  ))}
                </div>
              </div>

              {/* 证据 */}
              {detail.evidence && detail.evidence.length > 0 && (
                <div>
                  <h4 className="mb-2 text-sm font-semibold text-slate-700">支撑证据</h4>
                  <div className="space-y-2">
                    {detail.evidence.map((ev, i) => (
                      <div key={i} className="rounded-md bg-slate-50 p-3 text-xs">
                        <div className="font-semibold text-slate-700">{ev.claim || `证据 ${i + 1}`}</div>
                        <div className="mt-1 text-slate-500">{ev.text}</div>
                        <div className="mt-1 text-slate-400">来源: {ev.source || ev.metadata?.source || "简历片段"}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 优势+风险 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <h4 className="mb-1 text-sm font-semibold text-emerald-700">优势</h4>
                  <ul className="space-y-0.5 text-xs text-slate-600">
                    {detail.strengths?.map((s, i) => <li key={i}>{s}</li>) || <li className="text-slate-400">暂无</li>}
                  </ul>
                </div>
                <div>
                  <h4 className="mb-1 text-sm font-semibold text-rose-700">风险</h4>
                  <ul className="space-y-0.5 text-xs text-slate-600">
                    {detail.risks?.map((r, i) => <li key={i}>{r}</li>) || <li className="text-slate-400">暂无</li>}
                  </ul>
                </div>
              </div>

              {/* 总结 */}
              {detail.summary && (
                <div>
                  <h4 className="mb-1 text-sm font-semibold text-slate-700">匹配总结</h4>
                  <p className="text-sm leading-6 text-slate-600">{detail.summary}</p>
                </div>
              )}
            </div>
        )}
      </Modal>
    </div>
  );
}

function InterviewPanel({
  candidateId,
  candidateName,
  questions,
  evaluation,
  drafts,
  feedback,
  emailType,
  loading,
  onFeedbackChange,
  onEmailTypeChange,
  onGenerateQuestions,
  onSubmitEvaluation,
  onCreateDraft,
  onApproveDraft,
}: {
  candidateId: string;
  candidateName: string;
  questions: InterviewQuestion[];
  evaluation: InterviewEvaluation | null;
  drafts: EmailDraft[];
  feedback: string;
  emailType: "interview_invite" | "rejection" | "follow_up" | "next_round";
  loading: Record<string, boolean>;
  onFeedbackChange: (value: string) => void;
  onEmailTypeChange: (value: "interview_invite" | "rejection" | "follow_up" | "next_round") => void;
  onGenerateQuestions: () => void;
  onSubmitEvaluation: () => void;
  onCreateDraft: () => void;
  onApproveDraft: (emailId: string) => void;
}) {
  if (!candidateId) {
    return (
      <div className="glass-pad h-fit">
        <p className="section-label">面试跟进</p>
        <h3 className="mt-2 text-lg font-semibold text-slate-900">选择候选人</h3>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          匹配完成后，点击左侧候选人即可生成面试问题、提交反馈并创建邮件草稿。
        </p>
      </div>
    );
  }

  return (
    <aside className="glass-pad sticky top-24 h-fit space-y-5">
      <div>
        <p className="section-label">面试跟进</p>
        <h3 className="mt-2 text-lg font-semibold text-slate-950">{candidateName}</h3>
        <p className="mt-1 text-xs text-slate-400">{candidateId}</p>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white/70 p-4 backdrop-blur">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h4 className="text-sm font-semibold text-slate-900">面试问题</h4>
            <p className="mt-1 text-xs text-slate-500">围绕技术、项目和风险点生成问题。</p>
          </div>
          <LoadingButton onClick={onGenerateQuestions} loading={!!loading.questions} variant="secondary">
            生成
          </LoadingButton>
        </div>
        {questions.length > 0 ? (
          <div className="space-y-2">
            {questions.map((q) => (
              <div key={q.question_id || q.question} className="rounded-md bg-slate-50 p-3">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className="chip-blue">{questionTypeLabel(q.question_type)}</span>
                </div>
                <p className="text-sm font-medium leading-6 text-slate-800">{q.question}</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">{q.purpose}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="rounded-md bg-slate-50 p-3 text-sm text-slate-500">还没有生成面试问题。</p>
        )}
      </div>

      <div className="rounded-lg border border-slate-200 bg-white/70 p-4 backdrop-blur">
        <h4 className="text-sm font-semibold text-slate-900">面试评价</h4>
        <textarea
          value={feedback}
          onChange={(e) => onFeedbackChange(e.target.value)}
          rows={5}
          className="field mt-3 resize-y"
          placeholder="填写面试官反馈，例如技术回答、沟通表现、风险点是否澄清..."
        />
        <div className="mt-3">
          <LoadingButton onClick={onSubmitEvaluation} loading={!!loading.evaluation} disabled={!feedback.trim()}>
            生成评价
          </LoadingButton>
        </div>
        {evaluation && (
          <div className="mt-4 rounded-md bg-slate-50 p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="text-sm font-semibold text-slate-900">{evaluation.recommendation}</span>
              {evaluation.requires_human_review && <span className="chip">需人工审核</span>}
            </div>
            <p className="text-sm leading-6 text-slate-600">{evaluation.summary}</p>
            {evaluation.concerns?.length > 0 && (
              <div className="mt-3">
                <p className="mb-1 text-xs font-semibold text-rose-700">关注点</p>
                <ul className="space-y-1 text-xs text-slate-600">
                  {evaluation.concerns.map((item) => <li key={item}>{item}</li>)}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="rounded-lg border border-slate-200 bg-white/70 p-4 backdrop-blur">
        <h4 className="text-sm font-semibold text-slate-900">邮件草稿</h4>
        <div className="mt-3 flex gap-2">
          <select
            value={emailType}
            onChange={(e) => onEmailTypeChange(e.target.value as any)}
            className="field"
          >
            <option value="interview_invite">面试邀请</option>
            <option value="next_round">下一轮通知</option>
            <option value="follow_up">跟进邮件</option>
            <option value="rejection">拒信</option>
          </select>
          <LoadingButton onClick={onCreateDraft} loading={!!loading.draft}>
            生成
          </LoadingButton>
        </div>
        {drafts.length > 0 ? (
          <div className="mt-3 space-y-3">
            {drafts.map((draft) => (
              <div key={draft.email_id} className="rounded-md bg-slate-50 p-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-slate-900">{draft.subject}</span>
                  <span className={draft.status === "approved" ? "chip-green" : "chip"}>{draft.status}</span>
                </div>
                <pre className="max-h-36 overflow-auto whitespace-pre-wrap text-xs leading-5 text-slate-600">{draft.body}</pre>
                {draft.status !== "approved" && (
                  <div className="mt-3">
                    <LoadingButton
                      onClick={() => onApproveDraft(draft.email_id)}
                      loading={!!loading[`approve-${draft.email_id}`]}
                      variant="secondary"
                    >
                      批准草稿
                    </LoadingButton>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-3 rounded-md bg-slate-50 p-3 text-sm text-slate-500">还没有邮件草稿。</p>
        )}
      </div>
    </aside>
  );
}

function questionTypeLabel(type: string): string {
  const map: Record<string, string> = {
    technical: "技术",
    project_deep_dive: "项目深挖",
    behavioral: "行为",
    risk_verification: "风险验证",
  };
  return map[type] || type;
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
