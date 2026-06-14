// ================================================================
// JsonPanel 组件 — 结构化 JSON 数据展示面板
// 用于展示 JD Profile / Candidate Profile 等解析结果
// ================================================================

import { useState } from "react";

interface Props {
  title: string;
  data: Record<string, any> | null;
  defaultOpen?: boolean;
}

export default function JsonPanel({ title, data, defaultOpen = true }: Props) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  if (!data) return null;

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      {/* 标题栏 — 点击折叠/展开 */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <span className="text-sm font-medium text-gray-700">{title}</span>
        <span className="text-xs text-gray-400">{isOpen ? "收起 ▲" : "展开 ▼"}</span>
      </button>

      {/* 内容 */}
      {isOpen && (
        <div className="p-4 bg-white overflow-auto max-h-96">
          <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono leading-relaxed">
            {formatJson(data)}
          </pre>
        </div>
      )}
    </div>
  );
}

// ---- 辅助: 格式化 JSON 为可读文本 ----

function formatJson(obj: Record<string, any>, indent = 0): string {
  const prefix = "  ".repeat(indent);
  const lines: string[] = [];

  for (const [key, value] of Object.entries(obj)) {
    const keyStr = `${prefix}${key}: `;

    if (value === null || value === undefined) {
      lines.push(`${keyStr}—`);
    } else if (Array.isArray(value)) {
      if (value.length === 0) {
        lines.push(`${keyStr}[]`);
      } else {
        lines.push(`${keyStr}[`);
        value.forEach((item) => {
          if (typeof item === "object" && item !== null) {
            lines.push(`${prefix}  {`);
            lines.push(formatJson(item, indent + 2));
            lines.push(`${prefix}  },`);
          } else {
            lines.push(`${prefix}  ${String(item)},`);
          }
        });
        lines.push(`${prefix}]`);
      }
    } else if (typeof value === "object") {
      lines.push(`${keyStr}{`);
      lines.push(formatJson(value, indent + 1));
      lines.push(`${prefix}}`);
    } else {
      lines.push(`${keyStr}${String(value)}`);
    }
  }

  return lines.join("\n");
}
