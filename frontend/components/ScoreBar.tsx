// ================================================================
// ScoreBar 组件 — 分数进度条
// 根据分数显示不同颜色: 80+ 绿色, 65-79 蓝色, 50-64 黄色, <50 红色
// ================================================================

interface Props {
  score: number;
  maxScore?: number;
  label?: string;
}

/** 按分数段返回颜色 */
function scoreColor(score: number): string {
  if (score >= 80) return "bg-green-500";
  if (score >= 65) return "bg-blue-500";
  if (score >= 50) return "bg-yellow-500";
  return "bg-red-500";
}

export default function ScoreBar({ score, maxScore = 100, label }: Props) {
  // 百分比 (限制 0-100)
  const pct = Math.max(0, Math.min(100, (score / maxScore) * 100));

  return (
    <div className="w-full">
      {/* 标签 + 分数 */}
      <div className="flex justify-between text-sm mb-1">
        {label && <span className="text-gray-600">{label}</span>}
        <span className="font-semibold text-gray-800">{score}/{maxScore}</span>
      </div>
      {/* 进度条 */}
      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${scoreColor(score)}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
