// ================================================================
// StatusBadge 组件 — 推荐等级 / 状态徽章
// ================================================================

/** 推荐等级对应的颜色和中文 */
const LEVEL_MAP: Record<string, { cls: string; label: string }> = {
  "Strong Match":     { cls: "border-emerald-200 bg-emerald-50 text-emerald-700", label: "强烈推荐" },
  "Medium Match":     { cls: "border-sky-200 bg-sky-50 text-sky-700", label: "推荐面试" },
  "Weak Match":       { cls: "border-amber-200 bg-amber-50 text-amber-700", label: "可考虑" },
  "Not Recommended":  { cls: "border-rose-200 bg-rose-50 text-rose-700", label: "不推荐" },
};

interface Props {
  level: string;
}

export default function StatusBadge({ level }: Props) {
  const info = LEVEL_MAP[level] || { cls: "border-slate-200 bg-slate-50 text-slate-600", label: level };

  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${info.cls}`}>
      {info.label}
    </span>
  );
}
