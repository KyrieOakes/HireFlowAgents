// ================================================================
// LoadingButton 组件 — 带加载状态的按钮
// ================================================================

interface Props {
  onClick: () => void;
  loading: boolean;
  disabled?: boolean;
  children: React.ReactNode;
  variant?: "primary" | "secondary" | "danger";
}

const STYLES = {
  primary:   "bg-blue-600 text-white hover:bg-blue-700",
  secondary: "bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-300",
  danger:    "bg-red-600 text-white hover:bg-red-700",
};

export default function LoadingButton({
  onClick,
  loading,
  disabled = false,
  children,
  variant = "primary",
}: Props) {
  return (
    <button
      onClick={onClick}
      disabled={loading || disabled}
      className={
        `inline-flex items-center gap-2 px-4 py-2 rounded text-sm font-medium
         transition-colors disabled:opacity-50 disabled:cursor-not-allowed ` +
        STYLES[variant]
      }
    >
      {/* 加载动画 */}
      {loading && (
        <svg
          className="animate-spin h-4 w-4"
          viewBox="0 0 24 24"
          fill="none"
        >
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
      )}
      {children}
    </button>
  );
}
