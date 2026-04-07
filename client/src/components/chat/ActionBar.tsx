import { useState } from "react";
import { Pause, Play, RotateCcw } from "lucide-react";
import { useChatStore } from "../../stores/chatStore";
import { useTaskStore } from "../../stores/taskStore";
import { RestartDialog } from "./RestartDialog";

export function ActionBar() {
  const [restartOpen, setRestartOpen] = useState(false);
  const { isRunning, isPaused, isCollecting, events, pauseGraph, restartProject } =
    useChatStore();
  const { activeTaskId } = useTaskStore();

  const completed = events.some((e) => e.type === "task_complete");

  // 在收集、运行、暂停阶段均显示；完成后隐藏
  const visible = (isCollecting || isRunning || isPaused) && !completed;

  if (!visible || !activeTaskId) return null;

  const running = isRunning && !isPaused;

  // 收集阶段只显示状态，不显示操作按钮
  if (isCollecting) {
    return (
      <div className="mb-2 flex items-center gap-3 rounded-xl glass px-3 py-2 border border-border-subtle/60">
        <span className="h-2 w-2 rounded-full shrink-0 bg-status-success animate-pulse" />
        <span className="text-xs font-medium text-text-secondary">需求收集中</span>
      </div>
    );
  }

  return (
    <>
      <div className="mb-2 flex items-center justify-between gap-3 rounded-xl glass px-3 py-2 border border-border-subtle/60">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={`h-2 w-2 rounded-full shrink-0 ${running ? "bg-status-success" : "bg-status-warning"}`}
          />
          <span className="text-xs font-medium text-text-secondary truncate">
            {running ? "运行中" : "已暂停"}
          </span>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {running ? (
            <>
              <button
                type="button"
                onClick={() => pauseGraph()}
                className="flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-lg glass glass-hover text-text-primary"
              >
                <Pause size={12} />
                暂停
              </button>
              <button
                type="button"
                onClick={() => setRestartOpen(true)}
                className="flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-lg glass glass-hover text-text-secondary"
              >
                <RotateCcw size={12} />
                重启
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={() => useChatStore.getState().resumeGraph("继续执行")}
                className="flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-lg glass glass-hover text-status-success"
              >
                <Play size={12} />
                继续
              </button>
              <button
                type="button"
                onClick={() => setRestartOpen(true)}
                className="flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-lg glass glass-hover text-text-secondary"
              >
                <RotateCcw size={12} />
                重启
              </button>
            </>
          )}
        </div>
      </div>
      <RestartDialog
        open={restartOpen}
        onOpenChange={setRestartOpen}
        onConfirm={() => restartProject(activeTaskId)}
      />
    </>
  );
}
