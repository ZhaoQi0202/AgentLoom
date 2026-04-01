import { create } from "zustand";
import type { ChatEvent } from "../types";
import { graphSocket } from "../services/websocket";

interface ChatStore {
  events: ChatEvent[];
  currentPhase: string | null;
  isRunning: boolean;
  isInterrupted: boolean;
  isPaused: boolean;
  isCollecting: boolean;
  collectBuffer: string;

  addEvent: (event: ChatEvent) => void;
  clearEvents: () => void;
  startCollect: (taskId: string) => void;
  sendCollectMessage: (msg: string) => void;
  confirmStart: (taskId: string, userRequestFallback?: string) => void;
  startGraph: (taskId: string, userRequest?: string) => void;
  pauseGraph: () => void;
  resumeGraph: (feedback: string) => void;
}

export const useChatStore = create<ChatStore>((set, get) => ({
  events: [],
  currentPhase: null,
  isRunning: false,
  isInterrupted: false,
  isPaused: false,
  isCollecting: false,
  collectBuffer: "",

  addEvent: (event) =>
    set((s) => ({
      events: [...s.events, event],
      currentPhase:
        event.type === "phase_start"
          ? (event.phase ?? s.currentPhase)
          : s.currentPhase,
      isInterrupted: event.type === "hitl_interrupt",
      isRunning:
        event.type === "task_complete" || event.type === "error"
          ? false
          : s.isRunning,
    })),

  clearEvents: () =>
    set({
      events: [],
      currentPhase: null,
      isRunning: false,
      isInterrupted: false,
      isPaused: false,
      isCollecting: false,
      collectBuffer: "",
    }),

  startCollect: (_taskId: string) => {
    set({
      isCollecting: true,
      collectBuffer: "",
      isPaused: false,
      isRunning: false,
      isInterrupted: false,
    });
  },

  sendCollectMessage: (msg) => {
    const trimmed = msg.trim();
    if (!trimmed) return;
    set((s) => ({
      collectBuffer: s.collectBuffer ? `${s.collectBuffer}\n${trimmed}` : trimmed,
    }));
    get().addEvent({
      type: "user_response",
      timestamp: new Date().toISOString(),
      content: trimmed,
    });
  },

  confirmStart: (taskId, userRequestFallback) => {
    const buf = get().collectBuffer.trim();
    const userRequest = buf || userRequestFallback || taskId;
    set({ isCollecting: false, collectBuffer: "" });
    get().startGraph(taskId, userRequest);
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
    });
  },

  pauseGraph: () => {
    set({ isPaused: true });
  },

  resumeGraph: (feedback) => {
    graphSocket.send({ action: "resume", feedback });
    set({ isInterrupted: false, isPaused: false });
  },
}));
