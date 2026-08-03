// ================================================================
// Evidence ReAct Agent 轨迹面板
// 展示 Tool Calling、Observation、重试次数、证据覆盖率和人工处理选项
// ================================================================

import type {
  AgentInterventionAction,
  EvidenceAgentRun,
  EvidenceIntervention,
} from "@/types";


interface Props {
  /** 每个候选人的 Agent 运行记录。 */
  runs: EvidenceAgentRun[];
  /** 自动恢复失败后需要用户选择的问题。 */
  interventions: EvidenceIntervention[];
  /** 把候选人 ID 转换成人类可读姓名。 */
  candidateNames: Record<string, string>;
  /** 后端返回的本轮执行说明。 */
  message: string;
  /** 用户选择后重新运行时禁用按钮，防止重复请求。 */
  loading: boolean;
  /** 把人工选择交给匹配页重新调用后端。 */
  onResolve: (action: AgentInterventionAction) => void;
}


/** 根据 Agent 状态返回中文标签和颜色。 */
function statusStyle(status: EvidenceAgentRun["status"]): { label: string; className: string } {
  if (status === "completed") {
    return { label: "已完成", className: "border-emerald-200 bg-emerald-50 text-emerald-700" };
  }
  if (status === "insufficient_evidence") {
    return { label: "证据不足", className: "border-amber-200 bg-amber-50 text-amber-700" };
  }
  return { label: "等待人工", className: "border-rose-200 bg-rose-50 text-rose-700" };
}


/** 把评分维度字段转换成适合产品界面的中文。 */
function dimensionLabel(dimension: string): string {
  const labels: Record<string, string> = {
    technical_skills: "技术技能",
    project_relevance: "项目相关性",
    experience: "工作经验",
    education: "教育背景",
    domain_relevance: "领域相关性",
  };
  return labels[dimension] || dimension;
}


/** ReAct Agent 运行轨迹和人工介入卡片。 */
export default function AgentTracePanel({
  runs,
  interventions,
  candidateNames,
  message,
  loading,
  onResolve,
}: Props) {
  if (runs.length === 0 && interventions.length === 0) return null;

  const completed = runs.filter((run) => run.status === "completed").length;
  const insufficient = runs.filter((run) => run.status === "insufficient_evidence").length;
  const needsReview = runs.filter((run) => run.status === "needs_human_review").length;

  return (
    <section className="glass-pad" aria-labelledby="agent-trace-title">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="section-label">Bounded ReAct Agent</p>
          <h2 id="agent-trace-title" className="mt-2 text-lg font-semibold text-slate-950">
            证据 Agent 执行轨迹
          </h2>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-500">
            模型根据 Observation 动态选择简历检索工具；这里只展示可审计行动，不展示隐藏思维链。
          </p>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center text-xs">
          <div className="rounded-md bg-emerald-50 px-3 py-2 text-emerald-700">
            <div className="text-base font-semibold">{completed}</div>
            完成
          </div>
          <div className="rounded-md bg-amber-50 px-3 py-2 text-amber-700">
            <div className="text-base font-semibold">{insufficient}</div>
            证据不足
          </div>
          <div className="rounded-md bg-rose-50 px-3 py-2 text-rose-700">
            <div className="text-base font-semibold">{needsReview}</div>
            待处理
          </div>
        </div>
      </div>

      {message && (
        <p className="mt-4 rounded-md border border-slate-200 bg-white/70 px-3 py-2 text-sm text-slate-600">
          {message}
        </p>
      )}

      {interventions.length > 0 && (
        <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50/80 p-4">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-rose-100 text-sm font-bold text-rose-700">
              !
            </span>
            <div className="min-w-0 flex-1">
              <h3 className="text-sm font-semibold text-rose-900">自动重试已停止，需要人工选择</h3>
              <ul className="mt-2 space-y-1 text-xs leading-5 text-rose-800">
                {interventions.map((item) => (
                  <li key={`${item.candidate_id}-${item.error_code}`}>
                    <span className="font-semibold">
                      {candidateNames[item.candidate_id] || item.candidate_id}
                    </span>
                    ：{item.message}（{item.error_code}）
                  </li>
                ))}
              </ul>
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => onResolve("retry_agent")}
                  className="rounded-md bg-slate-950 px-3 py-2 text-xs font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  重试 Agent
                </button>
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => onResolve("continue_with_warning")}
                  className="rounded-md border border-amber-300 bg-white px-3 py-2 text-xs font-medium text-amber-800 transition hover:bg-amber-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  带警告继续
                </button>
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => onResolve("skip_failed")}
                  className="rounded-md border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  跳过失败候选人
                </button>
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => onResolve("abort")}
                  className="rounded-md px-3 py-2 text-xs font-medium text-rose-700 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  终止本轮
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="mt-4 space-y-3">
        {runs.map((run) => {
          const style = statusStyle(run.status);
          const candidateName = candidateNames[run.candidate_id] || run.candidate_id;

          return (
            <details key={run.candidate_id} className="group rounded-lg border border-slate-200 bg-white/70">
              <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-3 px-4 py-3">
                <div className="flex min-w-0 items-center gap-3">
                  <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${style.className}`}>
                    {style.label}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-slate-900">{candidateName}</p>
                    <p className="truncate text-xs text-slate-400">{run.candidate_id}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4 text-xs text-slate-500">
                  <span>{run.iterations} 轮决策</span>
                  <span>{run.tool_call_count} 次工具调用</span>
                  <span>{Math.round(run.coverage_rate * 100)}% 覆盖率</span>
                  <span className="transition group-open:rotate-180">⌄</span>
                </div>
              </summary>

              <div className="border-t border-slate-200 px-4 py-4">
                <div className="grid gap-3 md:grid-cols-3">
                  <div className="rounded-md bg-slate-50 p-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">停止原因</p>
                    <p className="mt-1 text-xs text-slate-700">{run.stop_reason}</p>
                  </div>
                  <div className="rounded-md bg-slate-50 p-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">覆盖维度</p>
                    <p className="mt-1 text-xs text-slate-700">
                      {run.covered_dimensions.map(dimensionLabel).join("、") || "暂无"}
                    </p>
                  </div>
                  <div className="rounded-md bg-slate-50 p-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">缺失维度</p>
                    <p className="mt-1 text-xs text-slate-700">
                      {run.missing_dimensions.map(dimensionLabel).join("、") || "无"}
                    </p>
                  </div>
                </div>

                <p className="mt-3 text-sm leading-6 text-slate-600">{run.reason_summary}</p>

                <div className="mt-4 space-y-2">
                  {run.tool_calls.map((call, index) => (
                    <div key={call.call_id} className="rounded-md border border-slate-200 bg-slate-50/70 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="flex h-6 w-6 items-center justify-center rounded bg-slate-900 text-[11px] font-semibold text-white">
                            {index + 1}
                          </span>
                          <span className="text-xs font-semibold text-slate-800">{call.tool_name}</span>
                          <span className="text-[11px] text-slate-400">第 {call.iteration} 轮</span>
                        </div>
                        <div className="flex gap-3 text-[11px] text-slate-400">
                          <span>尝试 {call.attempts} 次</span>
                          <span>{call.duration_ms}ms</span>
                        </div>
                      </div>
                      {typeof call.arguments.query === "string" && (
                        <p className="mt-2 text-xs text-slate-600">
                          <span className="font-medium text-slate-700">Query：</span>
                          {call.arguments.query}
                        </p>
                      )}
                      <p className={`mt-2 text-xs ${call.status === "failed" || call.status === "blocked" ? "text-rose-700" : "text-slate-500"}`}>
                        <span className="font-medium">Observation：</span>
                        {call.observation_summary}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </details>
          );
        })}
      </div>
    </section>
  );
}
