import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { IconSidebar, type NavPage } from "./components/layout/IconSidebar";
import { TaskList } from "./components/layout/TaskList";
import { RightPanel } from "./components/layout/RightPanel";
import { ChatArea } from "./components/chat/ChatArea";
import { ModelsPage } from "./components/config/ModelsPage";
import { McpPage } from "./components/config/McpPage";
import { SkillsPage } from "./components/config/SkillsPage";
import { SettingsPage } from "./components/config/SettingsPage";
import { TitleBar } from "./components/layout/TitleBar";
import { healthApi } from "./services/api";

export default function App() {
  const [page, setPage] = useState<NavPage>("tasks");
  const [backendReady, setBackendReady] = useState(false);
  const isTaskPage = page === "tasks";

  // 轮询后端健康检查
  useEffect(() => {
    let cancelled = false;
    async function poll() {
      while (!cancelled) {
        const ok = await healthApi.ping();
        if (ok) {
          setBackendReady(true);
          return;
        }
        await new Promise((r) => setTimeout(r, 800));
      }
    }
    poll();
    return () => { cancelled = true; };
  }, []);

  // 启动加载画面
  if (!backendReady) {
    return (
      <div className="flex flex-col h-screen w-screen overflow-hidden bg-bg-base">
        <TitleBar />
        <div className="flex-1 flex flex-col items-center justify-center gap-4">
          <div className="w-14 h-14 rounded-2xl gradient-brand animate-pulse flex items-center justify-center">
            <span className="text-white font-bold text-lg">AL</span>
          </div>
          <p className="text-text-secondary text-sm">正在启动后端服务...</p>
          <div className="flex gap-1">
            {[0, 1, 2].map((i) => (
              <motion.div
                key={i}
                className="w-2 h-2 rounded-full bg-brand-purple"
                animate={{ opacity: [0.3, 1, 0.3] }}
                transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  const mainContent: Record<NavPage, React.ReactNode> = {
    tasks: <ChatArea />,
    models: <ModelsPage />,
    mcp: <McpPage />,
    skills: <SkillsPage />,
    settings: <SettingsPage />,
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-bg-base">
      <TitleBar />
      <div className="flex flex-1 min-h-0">
        <IconSidebar activePage={page} onNavigate={setPage} />
        {isTaskPage && <TaskList />}
        <AnimatePresence mode="wait">
          <motion.main
            key={page}
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            transition={{ duration: 0.15 }}
            className="flex-1 flex flex-col min-w-0"
          >
            {mainContent[page]}
          </motion.main>
        </AnimatePresence>
        {isTaskPage && <RightPanel />}
      </div>
    </div>
  );
}
