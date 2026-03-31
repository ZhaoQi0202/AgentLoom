import { useState } from "react";

type NavPage = "tasks" | "models" | "mcp" | "skills" | "settings";

export default function App() {
  const [page, setPage] = useState<NavPage>("tasks");

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-bg-base">
      {/* Column 1: 图标侧栏 占位 */}
      <aside className="w-14 shrink-0 flex flex-col items-center py-4 gap-2 border-r border-border-subtle bg-bg-surface">
        <div className="w-8 h-8 rounded-lg gradient-brand flex items-center justify-center text-xs font-bold text-white">
          AL
        </div>
        <div className="flex-1" />
        <span className="text-text-muted text-[10px]">v0.1</span>
      </aside>

      {/* Column 2+3: 主区域占位 */}
      <main className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold gradient-brand-text mb-2">
            AgentLoom
          </h1>
          <p className="text-text-secondary">
            客户端 UI 重设计 — 脚手架已就绪
          </p>
          <p className="text-text-muted text-sm mt-4">
            当前页面: {page}
          </p>
        </div>
      </main>
    </div>
  );
}
