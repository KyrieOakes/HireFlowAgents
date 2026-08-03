// ================================================================
// 通用弹窗组件
// 使用 React Portal 把弹窗挂到 document.body，避免页面动画 transform
// 改变 fixed 定位基准，确保用户在长页面任意位置打开都能直接看到弹窗顶部。
// ================================================================

import { ReactNode, useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";


interface Props {
  /** 是否显示弹窗。 */
  open: boolean;
  /** 弹窗标题。 */
  title: string;
  /** 点击遮罩、关闭按钮或按 Esc 时执行。 */
  onClose: () => void;
  /** Tailwind 最大宽度，例如 max-w-xl、max-w-5xl。 */
  maxWidthClass?: string;
  /** 弹窗主体内容。 */
  children: ReactNode;
}


/** 提供统一的 Portal、焦点、Esc 关闭和弹窗内部滚动行为。 */
export default function Modal({
  open,
  title,
  onClose,
  maxWidthClass = "max-w-2xl",
  children,
}: Props) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    // 弹窗打开时禁止背景页面继续滚动，所有滚动都发生在弹窗内容区。
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    // 每次打开都把弹窗自身滚动位置归零，修复“还要往上滚才能看到标题”的问题。
    panelRef.current?.scrollTo({ top: 0 });

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [open, onClose]);

  // Next.js 服务端预渲染阶段没有 document，必须等到浏览器端再创建 Portal。
  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-start justify-center overflow-hidden bg-slate-950/40 p-4 backdrop-blur-sm sm:p-6"
      onClick={onClose}
      role="presentation"
    >
      <div
        ref={panelRef}
        className={`glass-panel soft-pop max-h-[calc(100vh-2rem)] w-full ${maxWidthClass} overflow-y-auto sm:max-h-[calc(100vh-3rem)]`}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white/90 px-5 py-4 backdrop-blur-xl">
          <h2 id={titleId} className="font-semibold text-slate-950">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-md text-xl text-slate-400 transition hover:bg-slate-100 hover:text-slate-800"
            aria-label="关闭弹窗"
          >
            ×
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  );
}
