// ================================================================
// 首页 Dashboard — 系统概览
// 展示: 岗位数量 / 候选人数量 / 快捷入口
// ================================================================

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/router";
import { listJobs, listCandidates } from "@/services/api";
import type { Job, Candidate } from "@/types";
import ErrorMessage from "@/components/ErrorMessage";

export default function Dashboard() {
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState(0); // 用于触发刷新

  // 每次页面可见时重新拉取数据 (包括从其他页面切回来)
  useEffect(() => {
    loadData();

    // 监听路由变化: 从其他页面切回首页时也刷新
    const handleRouteChange = (url: string) => {
      if (url === "/") loadData();
    };
    router.events.on("routeChangeComplete", handleRouteChange);
    return () => { router.events.off("routeChangeComplete", handleRouteChange); };
  }, [lastRefresh]);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [jobList, candidateList] = await Promise.all([
        listJobs(),
        listCandidates(),
      ]);
      setJobs(jobList);
      setCandidates(candidateList);
    } catch (e: any) {
      setError(e.message || "加载失败");
    } finally {
      setLoading(false);
    }
  }

  // 统计
  const parsedJobs = jobs.filter((j) => j.has_profile || j.jd_profile);
  const parsedCandidates = candidates.filter((c) => c.has_profile || c.profile);

  return (
    <div className="space-y-6 soft-enter">
      <div className="glass-pad overflow-hidden">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="section-label">HireFlow Command Center</p>
            <h1 className="page-title mt-2">招聘筛选工作台</h1>
            <p className="page-subtitle">
              管理岗位、候选人、匹配排名和面试跟进，一条流程完成从 JD 到邮件草稿的辅助决策。
            </p>
          </div>
          <button
            onClick={loadData}
            className="inline-flex items-center justify-center rounded-md border border-slate-300 bg-white/70 px-4 py-2 text-sm font-medium text-slate-700 shadow-sm backdrop-blur transition duration-200 hover:-translate-y-0.5 hover:bg-white"
          >
            刷新数据
          </button>
        </div>
      </div>

      {/* 错误提示 */}
      {error && <ErrorMessage message={error} onRetry={loadData} />}

      {/* 统计卡片 */}
      {!error && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard label="岗位总数" value={jobs.length} href="/jobs" accent="slate" />
          <StatCard label="已解析岗位" value={parsedJobs.length} hint={`/ ${jobs.length}`} href="/jobs" accent="sky" />
          <StatCard label="候选人总数" value={candidates.length} href="/resumes" accent="slate" />
          <StatCard label="已解析简历" value={parsedCandidates.length} hint={`/ ${candidates.length}`} href="/resumes" accent="emerald" />
        </div>
      )}

      {/* 快捷操作 */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <QuickCard title="创建岗位" desc="粘贴岗位描述，提取结构化 JD 和评分 Rubric" href="/jobs" step="01" disabled={false} />
        <QuickCard title="录入简历" desc="上传 PDF/DOCX/TXT，解析画像并建立 RAG 索引" href="/resumes" step="02" disabled={false} />
        <QuickCard
          title="匹配与面试"
          desc="执行排序，生成面试问题、评价和邮件草稿"
          href="/matching"
          step="03"
          disabled={parsedJobs.length === 0 || parsedCandidates.length === 0}
          disabledHint={!parsedJobs.length ? "请先解析岗位" : !parsedCandidates.length ? "请先解析简历" : undefined}
        />
      </div>

      {/* 流程提示 */}
      <div className="glass-pad">
        <p className="section-label mb-4">当前流程</p>
        <div className="grid gap-3 md:grid-cols-5">
          {["JD 解析", "简历画像", "RAG 证据", "匹配排序", "面试跟进"].map((step, index) => (
            <div key={step} className="rounded-lg border border-slate-200 bg-white/70 p-3 backdrop-blur">
              <div className="mb-2 flex h-7 w-7 items-center justify-center rounded-md bg-slate-950 text-xs font-semibold text-white">
                {index + 1}
              </div>
              <div className="text-sm font-semibold text-slate-800">{step}</div>
              <div className="mt-1 text-xs text-slate-500">{index < 4 ? "进入下一步" : "人工确认"}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---- 统计卡片 ----

function StatCard({
  label,
  value,
  hint,
  href,
  accent,
}: {
  label: string;
  value: number;
  hint?: string;
  href: string;
  accent: "slate" | "sky" | "emerald";
}) {
  const accentClass = {
    slate: "text-slate-950 bg-slate-100",
    sky: "text-sky-700 bg-sky-50",
    emerald: "text-emerald-700 bg-emerald-50",
  }[accent];

  return (
    <Link
      href={href}
      className="focus-card p-4"
    >
      <div className={`mb-3 inline-flex rounded-md px-2.5 py-1 text-xs font-semibold ${accentClass}`}>
        {label}
      </div>
      <div className="text-3xl font-semibold tracking-tight text-slate-950">
        {loadingNumber(value)}
        {hint && <span className="ml-1 text-sm font-normal text-slate-400">{hint}</span>}
      </div>
    </Link>
  );
}

function loadingNumber(value: number) {
  return Number.isFinite(value) ? value : 0;
}

// ---- 快捷操作卡片 ----

function QuickCard({
  title,
  desc,
  href,
  step,
  disabled,
  disabledHint,
}: {
  title: string;
  desc: string;
  href: string;
  step: string;
  disabled: boolean;
  disabledHint?: string;
}) {
  if (disabled) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white/45 p-5 opacity-70 backdrop-blur">
        <div className="mb-4 text-xs font-semibold text-slate-400">{step}</div>
        <h3 className="mb-1 font-semibold text-slate-500">{title}</h3>
        <p className="text-sm text-slate-400">{disabledHint || desc}</p>
      </div>
    );
  }

  return (
    <Link
      href={href}
      className="focus-card group p-5"
    >
      <div className="mb-4 flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-400">{step}</span>
        <span className="text-sm text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-sky-600">→</span>
      </div>
      <h3 className="mb-1 font-semibold text-slate-900">{title}</h3>
      <p className="text-sm leading-6 text-slate-500">{desc}</p>
    </Link>
  );
}
