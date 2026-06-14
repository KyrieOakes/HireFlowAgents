// ================================================================
// 首页 Dashboard — 系统概览
// 展示: 岗位数量 / 候选人数量 / 快捷入口
// ================================================================

import { useEffect, useState } from "react";
import Link from "next/link";
import { listJobs, listCandidates } from "@/services/api";
import type { Job, Candidate } from "@/types";
import ErrorMessage from "@/components/ErrorMessage";

export default function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 页面加载时获取数据
  useEffect(() => {
    loadData();
  }, []);

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
  const parsedJobs = jobs.filter((j) => j.jd_profile);
  const parsedCandidates = candidates.filter((c) => c.profile);

  return (
    <div>
      <h1 className="text-xl font-bold text-gray-800 mb-6">工作台</h1>

      {/* 错误提示 */}
      {error && <ErrorMessage message={error} onRetry={loadData} />}

      {/* 统计卡片 */}
      {!error && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard label="岗位总数" value={jobs.length} href="/jobs" />
          <StatCard label="已解析岗位" value={parsedJobs.length} hint={`/ ${jobs.length}`} href="/jobs" />
          <StatCard label="候选人总数" value={candidates.length} href="/resumes" />
          <StatCard label="已解析简历" value={parsedCandidates.length} hint={`/ ${candidates.length}`} href="/resumes" />
        </div>
      )}

      {/* 快捷操作 */}
      <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">快捷操作</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <QuickCard
          title="创建岗位"
          desc="粘贴岗位描述，调用 JD Agent 解析"
          href="/jobs"
          disabled={false}
        />
        <QuickCard
          title="录入简历"
          desc="粘贴简历文本，调用 Resume Agent 解析"
          href="/resumes"
          disabled={false}
        />
        <QuickCard
          title="执行匹配"
          desc="对候选人进行评分和排序"
          href="/matching"
          disabled={parsedJobs.length === 0 || parsedCandidates.length === 0}
          disabledHint={
            !parsedJobs.length
              ? "请先创建并解析岗位"
              : !parsedCandidates.length
                ? "请先录入并解析简历"
                : undefined
          }
        />
      </div>

      {/* 流程提示 */}
      <div className="mt-8 p-4 bg-blue-50 border border-blue-100 rounded-lg">
        <p className="text-sm text-blue-700">
          <span className="font-medium">使用流程:</span> 创建岗位 → 解析JD → 录入简历 → 解析简历 → 执行匹配 → 查看排名
        </p>
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
}: {
  label: string;
  value: number;
  hint?: string;
  href: string;
}) {
  return (
    <Link
      href={href}
      className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow transition-shadow"
    >
      <div className="text-2xl font-bold text-gray-800">
        {value}
        {hint && <span className="text-sm font-normal text-gray-400 ml-1">{hint}</span>}
      </div>
      <div className="text-sm text-gray-500 mt-1">{label}</div>
    </Link>
  );
}

// ---- 快捷操作卡片 ----

function QuickCard({
  title,
  desc,
  href,
  disabled,
  disabledHint,
}: {
  title: string;
  desc: string;
  href: string;
  disabled: boolean;
  disabledHint?: string;
}) {
  if (disabled) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 opacity-60 cursor-not-allowed">
        <h3 className="font-medium text-gray-500 mb-1">{title}</h3>
        <p className="text-xs text-gray-400">{disabledHint || desc}</p>
      </div>
    );
  }

  return (
    <Link
      href={href}
      className="bg-white border border-gray-200 rounded-lg p-4 hover:border-blue-300 hover:shadow transition-all"
    >
      <h3 className="font-medium text-gray-800 mb-1">{title}</h3>
      <p className="text-xs text-gray-500">{desc}</p>
    </Link>
  );
}
