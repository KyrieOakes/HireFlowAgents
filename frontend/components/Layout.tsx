// ================================================================
// Layout 组件 — 页面布局 + 顶部导航
// ================================================================

import Link from "next/link";
import { useRouter } from "next/router";

/** 导航菜单项 */
const NAV_ITEMS = [
  { href: "/", label: "工作台", short: "台" },
  { href: "/jobs", label: "岗位", short: "岗" },
  { href: "/resumes", label: "简历", short: "简" },
  { href: "/matching", label: "匹配与面试", short: "面" },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-slate-100">
      {/* ---- 顶部导航 ---- */}
      <nav className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4">
          {/* 品牌 */}
          <Link href="/" className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-950 text-sm font-semibold text-white">
              HF
            </span>
            <span>
              <span className="block text-base font-semibold tracking-tight text-slate-950">HireFlow</span>
              <span className="block text-[11px] font-medium uppercase tracking-wide text-slate-400">
                Recruiting Agents
              </span>
            </span>
          </Link>

          {/* 导航链接 */}
          <div className="flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 p-1">
            {NAV_ITEMS.map((item) => {
              const isActive = router.pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={
                    `flex min-w-10 items-center justify-center rounded-md px-3 py-2 text-sm transition-colors ` +
                    (isActive
                      ? "bg-white text-slate-950 shadow-sm font-medium"
                      : "text-slate-500 hover:text-slate-900")
                  }
                >
                  <span className="hidden sm:inline">{item.label}</span>
                  <span className="sm:hidden">{item.short}</span>
                </Link>
              );
            })}
          </div>
        </div>
      </nav>

      {/* ---- 页面内容 ---- */}
      <main className="mx-auto max-w-7xl px-4 py-6 lg:py-8">{children}</main>
    </div>
  );
}
