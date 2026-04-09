import type {
  LlmSettings,
  McpEntry,
  ModelConnection,
  SkillEntry,
  Task,
} from "../types";

const BASE = "http://127.0.0.1:9800/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

// ── 模型连接 ────────────────────────────────────────

export const modelConnectionsApi = {
  list: () => request<ModelConnection[]>("/config/model-connections"),

  create: (data: Omit<ModelConnection, "id">) =>
    request<ModelConnection>("/config/model-connections", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  remove: (id: string) =>
    request<{ status: string }>(`/config/model-connections/${id}`, {
      method: "DELETE",
    }),

  probe: (id: string) =>
    request<{ ok: boolean; message: string }>(
      `/config/model-connections/${id}/probe`,
      { method: "POST" },
    ),
};

// ── MCP 服务器 ──────────────────────────────────────

export const mcpApi = {
  list: () => request<McpEntry[]>("/config/mcps"),

  create: (data: McpEntry) =>
    request<McpEntry>("/config/mcps", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  remove: (id: string) =>
    request<{ status: string }>(`/config/mcps/${id}`, {
      method: "DELETE",
    }),
};

// ── 技能 ────────────────────────────────────────────

export const skillsApi = {
  list: () => request<SkillEntry[]>("/config/skills"),

  importSkill: (text: string) =>
    request<SkillEntry[]>("/config/skills/import", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),

  remove: (id: string) =>
    request<{ status: string }>(`/config/skills/${id}`, {
      method: "DELETE",
    }),
};

// ── LLM 设置 ───────────────────────────────────────

export const llmSettingsApi = {
  get: () => request<LlmSettings>("/config/llm-settings"),

  update: (data: LlmSettings) =>
    request<LlmSettings>("/config/llm-settings", {
      method: "PUT",
      body: JSON.stringify(data),
    }),
};

// ── 任务 ────────────────────────────────────────────

export const tasksApi = {
  list: () => request<Task[]>("/tasks"),

  create: (name: string) =>
    request<Task>("/tasks", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  remove: (id: string) =>
    request<{ status: string }>(`/tasks/${id}`, {
      method: "DELETE",
    }),

  getChatHistory: (taskId: string) =>
    request<ChatEvent[]>(`/tasks/${taskId}/chat-history`),
};

// ── 健康检查 ────────────────────────────────────────

export const healthApi = {
  check: () => request<{ status: string }>("/health".replace("/api", "")),
  ping: async (): Promise<boolean> => {
    try {
      const res = await fetch("http://127.0.0.1:9800/health", {
        signal: AbortSignal.timeout(2000),
      });
      return res.ok;
    } catch {
      return false;
    }
  },
};
