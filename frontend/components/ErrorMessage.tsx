// ================================================================
// ErrorMessage 组件 — 错误提示横幅
// ================================================================

interface Props {
  message: string;
  onRetry?: () => void;  // 可选的"重试"按钮
}

export default function ErrorMessage({ message, onRetry }: Props) {
  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
      {/* 图标 */}
      <span className="text-red-500 text-lg flex-shrink-0">⚠️</span>
      {/* 消息 */}
      <div className="flex-1 min-w-0">
        <p className="text-sm text-red-700">{message}</p>
        {message.includes("Failed to fetch") || message.includes("fetch") ? (
          <p className="text-xs text-red-400 mt-1">
            请确认后端已启动: uvicorn app.main:app --reload
          </p>
        ) : null}
      </div>
      {/* 重试按钮 */}
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-3 py-1 text-sm text-red-700 bg-red-100 rounded hover:bg-red-200 flex-shrink-0"
        >
          重试
        </button>
      )}
    </div>
  );
}
