// ================================================================
// Layout 组件 — 页面布局 + 顶部导航
// ================================================================

import Link from "next/link";
import { useRouter } from "next/router";

/** 导航菜单项 */
const NAV_ITEMS = [
  { href: "/", label: "首页" },
  { href: "/jobs", label: "岗位管理" },
  { href: "/resumes", label: "简历管理" },
  { href: "/matching", label: "匹配排名" },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* ---- 顶部导航 ---- */}
      <nav className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          {/* 品牌 */}
          <Link href="/" className="text-lg font-bold text-blue-700 tracking-tight">
            HireFlow
          </Link>

          {/* 导航链接 */}
          <div className="flex gap-1">
            {NAV_ITEMS.map((item) => {
              const isActive = router.pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={
                    `px-3 py-2 rounded text-sm transition-colors ` +
                    (isActive
                      ? "bg-blue-50 text-blue-700 font-medium"
                      : "text-gray-600 hover:text-gray-900 hover:bg-gray-100")
                  }
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        </div>
      </nav>

      {/* ---- 页面内容 ---- */}
      <main className="max-w-6xl mx-auto px-4 py-6">{children}</main>
    </div>
  );
}
