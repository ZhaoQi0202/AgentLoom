import { useEffect, useRef } from "react";
import { Play, Pause, RotateCcw } from "lucide-react";
import { useChatStore } from "../../stores/chatStore";
import { useTaskStore } from "../../stores/taskStore";
import { StatusBadge } from "../shared/StatusBadge";
import { SystemMessage } from "./SystemMessage";
import { AgentMessage } from "./AgentMessage";
import { UserMessage } from "./UserMessage";
import { HITLCard } from "./HITLCard";
import { ChatInput } from "./ChatInput";
import { AGENT_META, type AgentId, type ChatEvent } from "../../types";

export function ChatArea() {
  const { events, isRunning, isPaused, isInterrupted, isCollecting, startGraph, pauseGraph, clearEvents, startCollect, confirmStart } = useChatStore();
  const { activeTaskId, tasks } = useTaskStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  const activeTask = tasks.find((t) => t.id === activeTaskId);

  // 新消息自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events.length]);

  // 新项目组自动触发需求收集
  const prevTaskRef = useRef<string | null>(null);
  useEffect(() => {
    if (activeTask && activeTask.id !== prevTaskRef.current) {
      prevTaskRef.current = activeTask.id;
      if (events.length === 0 && !isRunning && !isCollecting) {
        startCollect(activeTask.id);
      }
    }
  }, [activeTask?.id]);

  // 未选择任务时的空状态
  if (!activeTask) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3">
        <div className="w-16 h-16 rounded-2xl gradient-brand opacity-20" />
        <p className="text-text-muted text-sm">选择一个项目组开始协作</p>
        <p className="text-text-disabled text-xs">或在左侧创建新项目组</p>
      </div>
    );
  }

  const status = isRunning
    ? "running"
    : isPaused
      ? "paused"
      : isInterrupted
        ? "paused"
        : events.some((e) => e.type === "task_complete")
          ? "completed"
          : "idle";

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* 顶部信息栏 */}
      <div className="shrink-0 flex items-center justify-between px-5 py-3 border-b border-border-subtle">
        <div className="flex items-center gap-3 min-w-0">
          <h2 className="text-base font-bold text-text-primary truncate">
            {activeTask.name}
          </h2>
          <StatusBadge status={status} />
        </div>
        <div className="flex items-center gap-2">
          {isCollecting && (
            <button
              onClick={() => confirmStart(activeTask.id, activeTask.name)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium glass glass-hover text-status-success"
            >
              <Play size={12} />
              启动项目
            </button>
          )}
          {isRunning && !isPaused && (
            <button
              onClick={pauseGraph}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium glass glass-hover text-status-warning"
            >
              <Pause size={12} />
              暂停项目
            </button>
          )}
          {isPaused && (
            <>
              <button
                onClick={() => {
                  useChatStore.getState().resumeGraph("继续执行");
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium glass glass-hover text-status-success"
              >
                <Play size={12} />
                继续项目
              </button>
              <button
                onClick={() => {
                  clearEvents();
                  startGraph(activeTask.id, activeTask.name);
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium glass glass-hover text-text-secondary"
              >
                <RotateCcw size={12} />
                重新开始
              </button>
            </>
          )}
          {!isRunning && !isPaused && !isCollecting && (
            <button
              onClick={() => {
                clearEvents();
                startGraph(activeTask.id, activeTask.name);
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium glass glass-hover text-status-success"
            >
              <Play size={12} />
              启动项目
            </button>
          )}
        </div>
      </div>

      {/* 对话区滚动容器 */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto py-4">
        {events.length === 0 && !isCollecting ? (
          <div className="flex flex-col items-center justify-center h-full gap-2">
            <p className="text-text-muted text-sm">新项目组已创建，等待启动...</p>
          </div>
        ) : (
          events.map((event, i) => {
            switch (event.type) {
              case "phase_start":
              case "phase_complete":
              case "task_complete":
                return <SystemMessage key={i} event={event} />;
              case "agent_thinking": {
                // Skip if a later agent_output from the same agent exists
                const hasLaterOutput = events.slice(i + 1).some(
                  (e) => e.type === "agent_output" && e.agent === event.agent
                );
                if (hasLaterOutput) return null;
                return <ThinkingBubble key={i} event={event} />;
              }
              case "agent_output":
                return <AgentMessage key={i} event={event} />;
              case "hitl_interrupt":
                return <HITLCard key={i} event={event} />;
              case "user_response":
                return <UserMessage key={i} event={event} />;
              case "error":
                return <ErrorCard key={i} event={event} />;
              default:
                return null;
            }
          })
        )}
      </div>

      {/* 底部输入区 */}
      <ChatInput />
    </div>
  );
}

function ErrorCard({ event }: { event: { content?: string; timestamp: string } }) {
  return (
    <div className="mx-4 my-2 p-3 border border-status-error/30 bg-status-error/5 rounded-[var(--radius-card)] text-sm text-status-error">
      {event.content || "发生错误"}
    </div>
  );
}

function ThinkingBubble({ event }: { event: ChatEvent }) {
  const meta = event.agent ? AGENT_META[event.agent as AgentId] : null;
  if (!meta) return null;

  return (
    <div className="flex gap-3 px-5 py-2">
      <div
        className="w-8 h-8 rounded-full flex items-center justify-center text-sm shrink-0"
        style={{ background: `linear-gradient(135deg, ${meta.gradient[0]}, ${meta.gradient[1]})` }}
      >
        {meta.emoji}
      </div>
      <div>
        <span className="text-xs font-semibold" style={{ color: meta.nameColor }}>
          {meta.label}
        </span>
        <div className="mt-1 px-3 py-2 rounded-[0_12px_12px_12px] glass">
          <div className="typing-dots">
            <span /><span /><span />
          </div>
        </div>
      </div>
    </div>
  );
}
