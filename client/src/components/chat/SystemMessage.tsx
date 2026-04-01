import type { ChatEvent } from "../../types";
import { AGENT_META } from "../../types";
import type { AgentId } from "../../types";

export function SystemMessage({ event }: { event: ChatEvent }) {
  const isJoin = event.type === "phase_start" && event.agent;
  const meta = event.agent ? AGENT_META[event.agent as AgentId] : null;

  if (isJoin && meta) {
    return (
      <div className="flex justify-center my-3">
        <span className="text-xs px-3 py-1 rounded-full bg-black/5 text-text-secondary">
          {meta.emoji} {meta.label} 加入群聊
        </span>
      </div>
    );
  }

  return (
    <div className="flex justify-center my-3">
      <span className="text-xs px-3 py-1 rounded-full bg-black/5 text-text-secondary">
        {event.content}
      </span>
    </div>
  );
}
