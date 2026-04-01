import { create } from "zustand";
import type { ChatEvent } from "../types";
import { graphSocket } from "../services/websocket";

interface ChatStore {
  events: ChatEvent[];
  currentPhase: string | null;
  isRunning: boolean;
  isPaused: boolean;
  isInterrupted: boolean;

  addEvent: (event: ChatEvent) => void;
  clearEvents: () => void;
  startGraph: (taskId: string, userRequest?: string) => void;
  pauseGraph: () => void;
  resumeGraph: (feedback: string) => void;
}

export const useChatStore = create<ChatStore>((set, get) => ({
  events: [],
  currentPhase: null,
  isRunning: false,
  isPaused: false,
  isInterrupted: false,

  addEvent: (event) =>
    set((s) => {
      const isPaused =
        event.type === "phase_complete" && event.content === "项目已暂停"
          ? true
          : s.isPaused;
      const isRunning =
        event.type === "task_complete" || event.type === "error"
          ? false
          : isPaused
            ? false
            : s.isRunning;
      return {
        events: [...s.events, event],
        currentPhase:
          event.type === "phase_start"
            ? (event.phase ?? s.currentPhase)
            : s.currentPhase,
        isInterrupted: event.type === "hitl_interrupt",
        isRunning,
        isPaused,
      };
    }),

  clearEvents: () =>
    set({
      events: [],
      currentPhase: null,
      isRunning: false,
      isPaused: false,
      isInterrupted: false,
    }),

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
    set({ isRunning: true, isPaused: false, isInterrupted: false, events: [] });
  },

  pauseGraph: () => {
    graphSocket.send({ action: "pause" });
  },

  resumeGraph: (feedback) => {
    graphSocket.send({ action: "resume", feedback });
    set({ isInterrupted: false, isPaused: false, isRunning: true });
  },
}));
