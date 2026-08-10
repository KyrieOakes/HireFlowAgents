// ================================================================
// 独立面试工作台路由
// 从动态 URL 中读取岗位和候选人 ID，再交给工作台组件加载对应数据。
// ================================================================

import { useRouter } from "next/router";
import InterviewWorkspace from "@/components/InterviewWorkspace";


/** 每个候选人拥有独立、可刷新、可直接访问的面试页面。 */
export default function CandidateInterviewPage() {
  const router = useRouter();
  // Next.js 动态路由参数可能是数组；不完整时不发送任何后端请求。
  const jobId = typeof router.query.jobId === "string" ? router.query.jobId : "";
  const candidateId = typeof router.query.candidateId === "string" ? router.query.candidateId : "";
  const returnThreadId = typeof router.query.returnThreadId === "string" ? router.query.returnThreadId : "";

  if (!router.isReady || !jobId || !candidateId) {
    return <div className="glass-pad text-center text-sm text-slate-500">正在读取面试工作台地址...</div>;
  }

  return (
    <InterviewWorkspace
      jobId={jobId}
      candidateId={candidateId}
      returnThreadId={returnThreadId}
    />
  );
}
