// ================================================================
// 匹配排名页 — 选择岗位 → 触发匹配 → 人工确认名单 → 进入独立面试工作台
// ================================================================

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/router";
import type {
  AgentInterventionAction,
  Candidate,
  EvidenceAgentRun,
  EvidenceIntervention,
  Job,
  MatchDetail,
  RankedCandidate,
  WorkflowProgressEvent,
  WorkflowResponse,
  WorkflowStatus,
} from "@/types";
import {
  listJobs,
  listCandidates,
  startMatchingWorkflow,
  streamMatchingWorkflow,
  resumeMatchingWorkflow,
  getMatchingWorkflowState,
  getMatchDetail,
} from "@/services/api";
import LoadingButton from "@/components/LoadingButton";
import ErrorMessage from "@/components/ErrorMessage";
import EmptyState from "@/components/EmptyState";
import StatusBadge from "@/components/StatusBadge";
import ScoreBar from "@/components/ScoreBar";
import AgentTracePanel from "@/components/AgentTracePanel";
import Modal from "@/components/Modal";


// 后端 phase 使用稳定英文值，页面集中映射为用户能直接理解的中文阶段名。
const PROGRESS_PHASE_LABELS: Record<string, string> = {
  loading: "读取数据",
  prescreening: "关键词粗排",
  indexing: "证据索引检查",
  evidence: "Evidence Agent",
  matching: "Match Agent",
  ranking: "Ranking Agent",
};

export default function MatchingPage() {
  const router = useRouter();
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
  // 切换岗位或组件卸载时关闭旧 SSE，避免不同任务的事件写进同一个页面。
  const progressAbortRef = useRef<AbortController | null>(null);
  // 从面试工作台返回时只恢复 URL 明确指定的任务，不能把普通进页面误判为恢复历史缓存。
  const returnRestoreHandledRef = useRef(false);
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
  // 三个数字分别展示粗排召回、LLM 精排和最终返回人数，方便验证两阶段排序真实发生。
  const [pipelineStats, setPipelineStats] = useState({ prescreened: 0, llmScored: 0, returned: 0 });
  // 选择岗位后只提示存在旧任务，由用户明确决定恢复还是开始新匹配。
  const [savedWorkflowThreadId, setSavedWorkflowThreadId] = useState("");
  const [workflowProgress, setWorkflowProgress] = useState<WorkflowProgressEvent | null>(null);

  // 动态路由参数可能是 string[]；这里只接受单个字符串，避免把错误参数传给后端。
  const returnJobId = typeof router.query.returnJobId === "string" ? router.query.returnJobId : "";
  const returnThreadId = typeof router.query.returnThreadId === "string" ? router.query.returnThreadId : "";

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

  // 用户点击工作台里的“返回面试名单”时，自动选回原岗位。
  // 这个行为依赖显式 URL 参数，不影响用户从导航栏新进入页面时的空白状态。
  useEffect(() => {
    if (!router.isReady || !returnJobId || !returnThreadId || returnRestoreHandledRef.current) return;
    setSelectedJobId(returnJobId);
  }, [router.isReady, returnJobId, returnThreadId]);

  // 用户切换岗位时清空当前展示；发现历史 thread_id 只显示选择框，不自动灌入旧排名。
  useEffect(() => {
    progressAbortRef.current?.abort();
    progressAbortRef.current = null;
    finishWorkflowRequest();
    resetWorkflowDisplay();

    if (!selectedJobId) {
      setSavedWorkflowThreadId("");
      return;
    }
    // 只有从独立面试工作台返回时才自动恢复本轮名单，保持返回动作的上下文连续性。
    if (
      returnJobId === selectedJobId
      && returnThreadId
      && !returnRestoreHandledRef.current
    ) {
      returnRestoreHandledRef.current = true;
      setSavedWorkflowThreadId("");
      void restoreWorkflowById(returnThreadId, selectedJobId);
      return;
    }

    const savedThreadId = window.localStorage.getItem(`hireflow-workflow:${selectedJobId}`) || "";
    setSavedWorkflowThreadId(savedThreadId);
  }, [selectedJobId, returnJobId, returnThreadId]);

  // 离开页面时关闭计时器和 SSE；后端任务仍可继续并保存 checkpoint。
  useEffect(() => () => {
    progressAbortRef.current?.abort();
    if (timerRef.current) clearInterval(timerRef.current);
  }, []);

  /** 清空某个岗位之前显示的排名和 Agent 轨迹。 */
  function resetWorkflowDisplay() {
    setRanked([]);
    setAgentRuns([]);
    setAgentInterventions([]);
    setAgentMessage("");
    setWorkflowStatus("");
    setWorkflowThreadId("");
    setReviewCandidateIds([]);
    setDefaultShortlistIds([]);
    setPipelineStats({ prescreened: 0, llmScored: 0, returned: 0 });
    setWorkflowProgress(null);
  }

  /** 把启动、恢复、状态查询的统一响应同步到页面。 */
  function applyWorkflowResponse(response: WorkflowResponse) {
    setWorkflowThreadId(response.thread_id || "");
    setWorkflowStatus(response.status);
    setAgentRuns(response.agent_runs || []);
    setAgentInterventions(response.interventions || []);
    setAgentMessage(response.message || "");
    setPipelineStats({
      prescreened: response.prescreened || 0,
      llmScored: response.llm_scored || 0,
      returned: response.returned || response.ranking?.ranked_candidates?.length || 0,
    });

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
    setWorkflowProgress(null);
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
    resetWorkflowDisplay();
    setSavedWorkflowThreadId("");
    try {
      const started = await startMatchingWorkflow(selectedJobId, limit);
      setWorkflowThreadId(started.thread_id);
      setWorkflowStatus(started.status);
      // POST 已经快速拿到 thread_id，此时立即保存；刷新后可以主动恢复后台任务。
      window.localStorage.setItem(`hireflow-workflow:${selectedJobId}`, started.thread_id);

      const controller = new AbortController();
      progressAbortRef.current = controller;
      const response = await streamMatchingWorkflow(
        started.thread_id,
        setWorkflowProgress,
        controller.signal,
      );
      applyWorkflowResponse(response);
    } catch (e: any) {
      if (e?.name !== "AbortError") setError(e.message);
    } finally {
      progressAbortRef.current = null;
      finishWorkflowRequest();
    }
  }

  /**
   * 按 thread_id 恢复一次任务。
   * jobId 参数用于清理失效的本地记录，既支持页面按钮，也支持从面试工作台返回。
   */
  async function restoreWorkflowById(threadId: string, jobId: string) {
    if (!threadId || matchLock.current) return;
    beginWorkflowRequest();
    try {
      const response = await getMatchingWorkflowState(threadId);
      if (response.status === "not_found") {
        window.localStorage.removeItem(`hireflow-workflow:${jobId}`);
        setSavedWorkflowThreadId("");
        throw new Error("上次任务已经不存在，请开始新匹配");
      }

      setWorkflowThreadId(threadId);
      if (response.progress) setWorkflowProgress(response.progress);
      if (response.status === "queued" || response.status === "running") {
        const controller = new AbortController();
        progressAbortRef.current = controller;
        const finalResponse = await streamMatchingWorkflow(
          threadId,
          setWorkflowProgress,
          controller.signal,
        );
        applyWorkflowResponse(finalResponse);
      } else {
        applyWorkflowResponse(response);
      }
      setSavedWorkflowThreadId("");
    } catch (e: any) {
      if (e?.name !== "AbortError") setError(e.message);
    } finally {
      progressAbortRef.current = null;
      finishWorkflowRequest();
    }
  }

  /** 用户明确选择“恢复上次任务”后，才读取 checkpoint 或重新订阅正在运行的 SSE。 */
  async function handleRestoreWorkflow() {
    await restoreWorkflowById(savedWorkflowThreadId, selectedJobId);
  }

  /** 放弃页面关联的旧 thread_id，但保留 PostgreSQL 历史记录并启动全新任务。 */
  async function handleStartNewWorkflow() {
    if (!selectedJobId) return;
    window.localStorage.removeItem(`hireflow-workflow:${selectedJobId}`);
    setSavedWorkflowThreadId("");
    await handleMatch();
  }

  /** 从当前 interrupt 恢复工作流；证据处理和最终排名审核都复用此函数。 */
  async function continueWorkflow(
    action: AgentInterventionAction | "approve_shortlist" | "reject" | "modify",
    selectedIds: string[] = [],
  ) {
    if (!workflowThreadId || matchLock.current) return;
    beginWorkflowRequest();
    try {
      const started = await resumeMatchingWorkflow(workflowThreadId, action, selectedIds);
      const controller = new AbortController();
      progressAbortRef.current = controller;
      const response = await streamMatchingWorkflow(
        started.thread_id,
        setWorkflowProgress,
        controller.signal,
      );
      applyWorkflowResponse(response);
    } catch (e: any) {
      if (e?.name !== "AbortError") setError(e.message);
    } finally {
      progressAbortRef.current = null;
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
            <p className="mt-1 text-sm text-slate-500">
              关键词召回候选池后，整池运行 Evidence 与 Match 精排，最后由 Ranking 返回 Top N。
            </p>
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
          <LoadingButton
            onClick={() => handleMatch()}
            loading={matching}
            disabled={!selectedJobId || Boolean(savedWorkflowThreadId)}
          >
            {savedWorkflowThreadId ? "请先选择处理方式" : "开始匹配"}
          </LoadingButton>
        </div>
        {savedWorkflowThreadId && !matching && (
          <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50/80 p-4">
            <p className="text-sm font-medium text-amber-900">发现这个岗位的上一次匹配任务</p>
            <p className="mt-1 text-xs text-amber-700">
              系统不会自动展示旧结果。你可以恢复原 checkpoint，也可以创建一个全新的 thread。
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={handleRestoreWorkflow}
                className="rounded-md bg-amber-600 px-3 py-2 text-sm font-medium text-white hover:bg-amber-700"
              >
                恢复上次任务
              </button>
              <button
                type="button"
                onClick={handleStartNewWorkflow}
                className="rounded-md border border-amber-300 bg-white px-3 py-2 text-sm font-medium text-amber-800 hover:bg-amber-100"
              >
                开始新匹配
              </button>
            </div>
          </div>
        )}
        {/* 匹配进度提示 */}
        {matching && (
          <div className="mt-4 rounded-lg border border-sky-200 bg-sky-50/80 p-4 backdrop-blur">
            <div className="flex items-start gap-3">
              <svg className="animate-spin h-5 w-5 text-blue-600" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm font-medium text-sky-800">
                    {workflowProgress
                      ? PROGRESS_PHASE_LABELS[workflowProgress.phase] || workflowProgress.phase
                      : "正在创建后台任务"}
                  </span>
                  <span className="text-xs text-sky-600">已等待 {elapsed} 秒</span>
                </div>
                <p className="mt-1 text-sm text-sky-700">
                  {workflowProgress?.message || "正在等待后端返回第一条真实进度"}
                </p>
                {workflowProgress && workflowProgress.total > 0 && (
                  <div className="mt-3">
                    <div className="mb-1 flex justify-between text-xs text-sky-600">
                      <span>{workflowProgress.candidate_name || "阶段进度"}</span>
                      <span>{workflowProgress.completed} / {workflowProgress.total}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-sky-100">
                      <div
                        className="h-full rounded-full bg-sky-500 transition-all duration-300"
                        style={{
                          width: `${Math.min(100, Math.max(0, workflowProgress.completed / workflowProgress.total * 100))}%`,
                        }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
        {!matching && pipelineStats.prescreened > 0 && (
          <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-600">
            <span className="rounded-full bg-slate-100 px-3 py-1.5">关键词召回 {pipelineStats.prescreened} 人</span>
            <span className="rounded-full bg-sky-100 px-3 py-1.5 text-sky-700">证据 + LLM 精排 {pipelineStats.llmScored} 人</span>
            <span className="rounded-full bg-emerald-100 px-3 py-1.5 text-emerald-700">最终返回 {pipelineStats.returned} 人</span>
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
          <div className="space-y-4">
            {visibleRanked.map((c, i) => (
              <div
                key={c.candidate_id}
                className="focus-card p-4"
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
                        加入面试名单
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

                {/* 每个动作都使用独立按钮，避免点击整张卡片后页面在未知位置发生变化。 */}
                <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
                  <p className="text-xs leading-5 text-slate-500">
                    {workflowStatus === "completed"
                      ? "名单已确认，可以进入该候选人的独立面试流程。"
                      : "确认最终面试名单后，才会开放面试工作台。"}
                  </p>
                  <div className="flex flex-wrap gap-2">
                  <LoadingButton
                    onClick={() => handleDetail(c.candidate_id)}
                    loading={detailLoading && detailId === c.candidate_id}
                    variant="secondary"
                  >
                    详细评分
                  </LoadingButton>
                    {workflowStatus === "completed" && (
                      <button
                        type="button"
                        onClick={() => {
                          void router.push({
                            pathname: "/interviews/[jobId]/[candidateId]",
                            query: {
                              jobId: selectedJobId,
                              candidateId: c.candidate_id,
                              returnThreadId: workflowThreadId,
                            },
                          });
                        }}
                        className="inline-flex items-center gap-2 rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:-translate-y-0.5 hover:bg-slate-800 active:translate-y-0"
                      >
                        进入面试工作台
                        <span aria-hidden="true">→</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
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
