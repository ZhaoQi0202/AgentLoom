import { Minus, Square, X } from "lucide-react";

declare global {
  interface Window {
    electronAPI?: {
      minimize: () => void;
      maximize: () => void;
      close: () => void;
      checkBackend: () => Promise<boolean>;
    };
  }
}

export function TitleBar() {
  const isElectron = !!window.electronAPI;

  return (
    <div className="h-8 shrink-0 flex items-center bg-bg-surface border-b border-border-subtle drag-region select-none">
      {/* 左侧占位，与侧栏对齐 */}
      <div className="w-14 shrink-0" />

      {/* 标题 */}
      <div className="flex-1 text-center">
        <span className="text-xs text-text-muted font-medium tracking-wide">
          AgentLoom
        </span>
      </div>

      {/* 窗口控制按钮 */}
      {isElectron && (
        <div className="flex items-center no-drag">
          <button
            onClick={() => window.electronAPI?.minimize()}
            className="w-11 h-8 flex items-center justify-center text-text-muted hover:bg-bg-hover hover:text-text-secondary transition-colors"
          >
            <Minus size={14} />
          </button>
          <button
            onClick={() => window.electronAPI?.maximize()}
            className="w-11 h-8 flex items-center justify-center text-text-muted hover:bg-bg-hover hover:text-text-secondary transition-colors"
          >
            <Square size={12} />
          </button>
          <button
            onClick={() => window.electronAPI?.close()}
            className="w-11 h-8 flex items-center justify-center text-text-muted hover:bg-status-error hover:text-white transition-colors"
          >
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
