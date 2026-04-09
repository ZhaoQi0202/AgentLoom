import { create } from "zustand";
import type { ChatEvent } from "../types";
import { graphSocket } from "../services/websocket";
import { tasksApi } from "../services/api";

const MIN_DISPLAY_MS = 2000;

interface ChatStore {
  events: ChatEvent[];
  pendingEvents: ChatEvent[];
  currentPhase: string | null;
  isRunning: boolean;
  isInterrupted: boolean;
  isPaused: boolean;
  isCollecting: boolean;
  isConsultantThinking: boolean;

  addEvent: (event: ChatEvent) => void;
  clearEvents: () => void;
  startCollect: (taskId: string) => void;
  sendCollectMessage: (msg: string) => void;
  startGraph: (taskId: string, userRequest?: string) => void;
  pauseGraph: () => void;
  resumeGraph: (feedback: string) => void;
  restartProject: (taskId: string) => void;
}

export const useChatStore = create<ChatStore>((set, get) => ({
  events: [],
  pendingEvents: [],
  currentPhase: null,
  isRunning: false,
  isInterrupted: false,
  isPaused: false,
  isCollecting: false,
  isConsultantThinking: false,

  addEvent: (event) => {
    // 去重：如果 events 中已有相同事件则跳过
    const isDuplicate = get().events.some(
      (e) =>
        e.timestamp === event.timestamp &&
        e.type === event.type &&
        e.content === event.content
    );
    if (isDuplicate) return;

    // agent_output 走延迟队列，其余直接加入 events
    if (event.type === "agent_output") {
      const arrivalTs = Date.now();
      set((s) => ({ pendingEvents: [...s.pendingEvents, event] }));

      const elapsed = Date.now() - arrivalTs;
      const delay = Math.max(0, MIN_DISPLAY_MS - elapsed);

      setTimeout(() => {
        set((s) => ({
          pendingEvents: s.pendingEvents.filter((e) => e !== event),
          events: [...s.events, event],
          isConsultantThinking: s.isCollecting ? false : s.isConsultantThinking,
          isRunning:
            event.type === "task_complete" || event.type === "error"
              ? false
              : s.isRunning,
        }));
      }, delay);
      return;
    }

    // 非 agent_output：直接处理
    set((s) => {
      const isConsultantThinking =
        event.type === "agent_thinking" && s.isCollecting
          ? true
          : s.isConsultantThinking;

      const architectJoin =
        event.type === "agent_join" && event.agent === "architect";

      return {
        events: [...s.events, event],
        currentPhase:
          event.type === "phase_start" || event.type === "agent_join"
            ? (event.phase ?? s.currentPhase)
            : s.currentPhase,
        isInterrupted: event.type === "hitl_interrupt" ? true : s.isInterrupted,
        isRunning: architectJoin
          ? true
          : event.type === "task_complete" || event.type === "error"
            ? false
            : s.isRunning,
        isCollecting: architectJoin ? false : s.isCollecting,
        isConsultantThinking,
      };
    });
  },

  clearEvents: () =>
    set({
      events: [],
      pendingEvents: [],
      currentPhase: null,
      isRunning: false,
      isInterrupted: false,
      isPaused: false,
      isCollecting: false,
      isConsultantThinking: false,
    }),

  startCollect: async (taskId: string) => {
    // 拉取历史
    let historyEvents: ChatEvent[] = [];
    try {
      historyEvents = await tasksApi.getChatHistory(taskId);
    } catch { /* 忽略错误 */ }

    const sessionId = crypto.randomUUID();
    set({
      isCollecting: true,
      isConsultantThinking: false,
      isPaused: false,
      isRunning: false,
      isInterrupted: false,
      events: historyEvents,
      pendingEvents: [],
    });
    graphSocket.connect(sessionId, {
      initial: { action: "collect", task_id: taskId, message: "" },
      onEvent: (event) => get().addEvent(event),
    });
  },

  sendCollectMessage: (msg) => {
    const trimmed = msg.trim();
    if (!trimmed) return;
    get().addEvent({
      type: "user_response",
      timestamp: new Date().toISOString(),
      content: trimmed,
    });
    graphSocket.send({
      action: "collect",
      task_id: "",
      message: trimmed,
    });
  },

  startGraph: (taskId, userRequest) => {
    const sessionId = crypto.randomUUID();
    graphSocket.connect(sessionId, {
      initial: {
        action: "start",
        task_id: taskId,
        user_request: userRequest || taskId,
      },
      onEvent: (event) => get().addEvent(event),
    });
    set({
      isRunning: true,
      isInterrupted: false,
      isPaused: false,
      isCollecting: false,
      events: [],
      pendingEvents: [],
    });
  },

  pauseGraph: () => {
    set({ isPaused: true });
  },

  resumeGraph: (feedback) => {
    graphSocket.send({ action: "resume", feedback });
    set({ isInterrupted: false, isPaused: false });
  },

  restartProject: (taskId: string) => {
    graphSocket.disconnect();
    get().clearEvents();
    get().startCollect(taskId);
  },
}));
