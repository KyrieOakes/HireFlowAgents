// ================================================================
// StatusBadge 组件 — 推荐等级 / 状态徽章
// ================================================================

/** 推荐等级对应的颜色和中文 */
const LEVEL_MAP: Record<string, { bg: string; text: string; label: string }> = {
  "Strong Match":     { bg: "bg-green-100", text: "text-green-800", label: "强烈推荐" },
  "Medium Match":     { bg: "bg-blue-100",  text: "text-blue-800",  label: "推荐面试" },
  "Weak Match":       { bg: "bg-yellow-100", text: "text-yellow-800", label: "可考虑" },
  "Not Recommended":  { bg: "bg-red-100",   text: "text-red-800",   label: "不推荐" },
};

interface Props {
  level: string;
}

export default function StatusBadge({ level }: Props) {
  const info = LEVEL_MAP[level] || { bg: "bg-gray-100", text: "text-gray-600", label: level };

  return (
    <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${info.bg} ${info.text}`}>
      {info.label}
    </span>
  );
}
