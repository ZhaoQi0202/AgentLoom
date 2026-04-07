import type { ChatEvent } from "../types";

type EventHandler = (event: ChatEvent) => void;

const WS_BASE = "ws://127.0.0.1:9800/api";

export class GraphSocket {
  private ws: WebSocket | null = null;
  private handlers = new Set<EventHandler>();

  connect(
    sessionId: string,
    options?: {
      initial?: Record<string, unknown>;
      onEvent?: EventHandler;
    },
  ) {
    // 先关掉旧连接，但要捕获旧 ws 引用，避免其 onclose 覆盖新 ws
    const oldWs = this.ws;
    if (oldWs) {
      oldWs.onclose = null;
      oldWs.onmessage = null;
      oldWs.onerror = null;
      oldWs.close();
    }
    this.handlers.clear();
    if (options?.onEvent) {
      this.handlers.add(options.onEvent);
    }

    const url = `${WS_BASE}/ws/graph/${sessionId}`;
    const ws = new WebSocket(url);
    this.ws = ws;

    ws.onopen = () => {
      if (options?.initial && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(options.initial));
      }
    };

    ws.onmessage = (e) => {
      try {
        const event: ChatEvent = JSON.parse(e.data);
        this.handlers.forEach((h) => h(event));
      } catch {
        console.error("[GraphSocket] Failed to parse message:", e.data);
      }
    };

    ws.onclose = () => {
      if (this.ws === ws) {
        this.ws = null;
      }
    };

    ws.onerror = (err) => {
      console.error("[GraphSocket] Error:", err);
    };
  }

  send(data: Record<string, unknown>) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  subscribe(handler: EventHandler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  disconnect() {
    const ws = this.ws;
    if (ws) {
      ws.onclose = null;
      ws.onmessage = null;
      ws.onerror = null;
      ws.close();
      this.ws = null;
    }
  }

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

export const graphSocket = new GraphSocket();
