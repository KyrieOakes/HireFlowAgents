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
    <div className="text-center py-12 px-4">
      {/* 图标 */}
      <div className="text-4xl mb-3 text-gray-300">📋</div>
      {/* 标题 */}
      <h3 className="text-lg font-medium text-gray-500 mb-1">{title}</h3>
      {/* 描述 */}
      {description && (
        <p className="text-sm text-gray-400 mb-4">{description}</p>
      )}
      {/* 操作按钮 */}
      {action && onAction && (
        <button
          onClick={onAction}
          className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 transition-colors"
        >
          {action}
        </button>
      )}
    </div>
  );
}
