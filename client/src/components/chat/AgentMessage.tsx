import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import type { ChatEvent, AgentId } from "../../types";
import { AGENT_META } from "../../types";
import { AgentAvatar } from "../shared/AgentAvatar";

interface AgentMessageProps {
  event: ChatEvent;
}

export function AgentMessage({ event }: AgentMessageProps) {
  const agentId = (event.agent || "consultant") as AgentId;
  const meta = AGENT_META[agentId];
  const isThinking = event.type === "agent_thinking";

  const time = new Date(event.timestamp).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex gap-3 px-4 py-2 max-w-[85%]"
    >
      <AgentAvatar agentId={agentId} size={36} />
      <div className="min-w-0 flex-1">
        {/* 头部：Agent 名称 + 时间 */}
        <div className="flex items-baseline gap-2 mb-1">
          <span className="text-sm font-semibold" style={{ color: meta.nameColor }}>
            {meta.emoji} {meta.label}
          </span>
          <span className="text-[10px] text-text-muted">{time}</span>
        </div>

        {/* 消息气泡 */}
        <div className="bg-white/80 backdrop-blur-sm border border-black/5 shadow-sm rounded-tl-sm p-3 text-sm text-text-body leading-relaxed">
          {isThinking ? (
            <ThinkingDots />
          ) : (
            <div className="prose prose-sm max-w-none [&>p]:my-1 [&>ul]:my-1 [&>ol]:my-1">
              <ReactMarkdown>{event.content || ""}</ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

function ThinkingDots() {
  return (
    <div className="flex items-center gap-1 py-1">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="w-2 h-2 rounded-full bg-text-muted"
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{
            duration: 1.2,
            repeat: Infinity,
            delay: i * 0.2,
          }}
        />
      ))}
    </div>
  );
}
