import { useState, useRef, useEffect } from "react";
import { Send } from "lucide-react";
import { useChatStore } from "../../stores/chatStore";
import { ActionBar } from "./ActionBar";

export function ChatInput() {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { isInterrupted, isRunning, isCollecting, isConsultantThinking, quickReplies, resumeGraph, sendCollectMessage, addEvent, sendDecision } = useChatStore();

  // HITL 中断时自动聚焦输入框
  useEffect(() => {
    if (isInterrupted || isCollecting) {
      textareaRef.current?.focus();
    }
  }, [isInterrupted, isCollecting]);

  const handleSend = () => {
    const msg = text.trim();
    if (!msg) return;

    if (isCollecting) {
      sendCollectMessage(msg);
      setText("");
      return;
    }

    // 添加用户消息到对话流
    addEvent({
      type: "user_response",
      timestamp: new Date().toISOString(),
      content: msg,
    });

    // 恢复图谱执行
    resumeGraph(msg);
    setText("");
  };

  const handleQuickReply = (reply: string) => {
    addEvent({
      type: "user_response",
      timestamp: new Date().toISOString(),
      content: reply,
    });
    sendDecision(reply);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const canSend = text.trim().length > 0 && (isCollecting || isInterrupted || !isRunning) && !isConsultantThinking;

  return (
    <div className="p-4 border-t border-border-subtle">
      {/* 快捷回复按钮 */}
      {quickReplies.length > 0 && (
        <div className="flex gap-2 mb-2 flex-wrap">
          {quickReplies.map((reply) => (
            <button
              key={reply}
              onClick={() => handleQuickReply(reply)}
              className="px-3 py-1.5 text-xs font-medium rounded-lg glass glass-hover text-text-primary border border-border-subtle"
            >
              {reply}
            </button>
          ))}
        </div>
      )}
      <ActionBar />
      <div className="glass flex items-end gap-2 p-2">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isConsultantThinking ? "需求分析师正在思考..." : isCollecting ? "回复需求分析师..." : isInterrupted ? "回复 Agent..." : "输入消息与 Agent 对话..."}
          rows={1}
          className="flex-1 bg-transparent outline-none text-sm text-text-primary placeholder:text-text-disabled resize-none max-h-32 py-1.5 px-2 min-h-[28px]"
          style={{ fieldSizing: "content" } as React.CSSProperties}
        />
        <button
          onClick={handleSend}
          disabled={!canSend}
          className={`
            w-8 h-8 rounded-lg flex items-center justify-center shrink-0 transition-all duration-150
            ${canSend
              ? "gradient-brand text-white hover:opacity-90"
              : "bg-bg-elevated text-text-disabled cursor-not-allowed"
            }
          `}
        >
          <Send size={14} />
        </button>
      </div>
    </div>
  );
}
