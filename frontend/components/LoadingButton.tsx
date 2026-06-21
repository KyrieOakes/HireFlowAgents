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
  primary:   "bg-slate-950 text-white hover:bg-slate-800 shadow-sm",
  secondary: "bg-white/80 text-slate-700 hover:bg-white border border-slate-300 shadow-sm backdrop-blur",
  danger:    "bg-rose-600 text-white hover:bg-rose-700 shadow-sm",
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
        `inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium
         transition duration-200 hover:-translate-y-0.5 active:translate-y-0
         disabled:translate-y-0 disabled:cursor-not-allowed disabled:opacity-50 ` +
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
