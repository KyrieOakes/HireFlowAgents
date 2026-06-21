// ================================================================
// EmptyState 组件 — 空状态提示
// 当列表为空或某步骤未完成时显示
// ================================================================

interface Props {
  title: string;
  description?: string;
  action?: string;    // 操作按钮文案
  onAction?: () => void; // 操作按钮回调
}

export default function EmptyState({ title, description, action, onAction }: Props) {
  return (
    <div className="glass-pad soft-enter px-4 py-12 text-center">
      {/* 图标 */}
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-lg border border-slate-200 bg-white/80 text-xl text-slate-400 shadow-sm">
        □
      </div>
      {/* 标题 */}
      <h3 className="mb-1 text-lg font-semibold text-slate-700">{title}</h3>
      {/* 描述 */}
      {description && (
        <p className="mb-4 text-sm text-slate-500">{description}</p>
      )}
      {/* 操作按钮 */}
      {action && onAction && (
        <button
          onClick={onAction}
          className="rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-slate-800"
        >
          {action}
        </button>
      )}
    </div>
  );
}
