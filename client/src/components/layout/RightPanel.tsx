import { useChatStore } from "../../stores/chatStore";
import { AGENT_META, WORKFLOW_PHASES, type AgentId, type ChatEvent } from "../../types";
import { AgentAvatar } from "../shared/AgentAvatar";
import { GlassCard } from "../shared/GlassCard";

// 四阶段面板定义
const PHASE_PANELS = [
  { key: "consult", label: "需求收集", agentIds: ["consultant"] as AgentId[] },
  { key: "architect", label: "架构规划", agentIds: ["architect"] as AgentId[] },
  { key: "execute", label: "执行", agentIds: ["experts"] as AgentId[] },
  { key: "review", label: "审核", agentIds: ["reviewer"] as AgentId[] },
] as const;

const PHASE_ORDER = ["consult", "architect", "execute", "review"];

function getPhaseStatus(
  phaseKey: string,
  events: ChatEvent[],
  currentPhase: string | null,
  isRunning: boolean,
  isCollecting: boolean,
): "pending" | "active" | "completed" | "error" {
  const hasPhaseEvent = events.some(
    (e) => e.phase === phaseKey && (e.type === "agent_output" || e.type === "agent_join")
  );
  const hasNextPhase = events.some(
    (e) =>
      e.phase !== phaseKey &&
      e.type === "agent_join" &&
      PHASE_ORDER.indexOf(e.phase || "") > PHASE_ORDER.indexOf(phaseKey)
  );
  const hasError = events.some(
    (e) => e.phase === phaseKey && e.type === "error"
  );

  if (hasError) return "error";
  if (hasPhaseEvent && hasNextPhase) return "completed";
  if (hasPhaseEvent || currentPhase === phaseKey) return "active";
  // 特殊：collecting 阶段
  if (phaseKey === "consult" && isCollecting) return "active";
  return "pending";
}

interface DynamicAgent {
  name: string;
  color: string;
  taskId: string;
  status: string;
}

function extractDynamicAgents(events: ChatEvent[]): DynamicAgent[] {
  const agents: DynamicAgent[] = [];
  const seenDynamic = new Set<string>();

  for (const e of events) {
    const agentName = (e.agent_name || e.metadata?.agent_name) as string | undefined;
    const agentColor = (e.agent_color) as string | undefined;
    const taskId = e.metadata?.task_id as string | undefined;
    if (agentName && taskId && !seenDynamic.has(taskId)) {
      seenDynamic.add(taskId);
      agents.push({
        name: agentName,
        color: agentColor || "#0891b2",
        taskId,
        status: "running",
      });
    }
  }

  // 标记已完成的
  for (const e of events) {
    const taskId = e.metadata?.task_id as string | undefined;
    if (taskId && e.content?.includes("执行完毕")) {
      const agent = agents.find((a) => a.taskId === taskId);
      if (agent) agent.status = e.content.includes("✅") ? "completed" : "error";
    }
  }

  return agents;
}

export function RightPanel() {
  const { currentPhase, events, isRunning, isCollecting } = useChatStore();
  const dynamicAgents = extractDynamicAgents(events);

  return (
    <aside className="w-[260px] shrink-0 border-l border-border-subtle bg-bg-surface/50 flex flex-col overflow-y-auto">
      {/* 四阶段面板 */}
      <div className="p-4 border-b border-border-subtle">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
          工作流进度
        </h3>
        <div className="space-y-3">
          {PHASE_PANELS.map((phase) => {
            const status = getPhaseStatus(
              phase.key, events, currentPhase, isRunning, isCollecting
            );
            return (
              <GlassCard
                key={phase.key}
                className={`p-3 ${
                  status === "active" ? "ring-1 ring-brand-purple/30" : ""
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-text-primary">
                    {phase.label}
                  </span>
                  <StatusDot status={status} />
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {phase.agentIds.map((agentId) => {
                    const meta = AGENT_META[agentId];
                    return (
                      <div key={agentId} className="flex items-center gap-1.5">
                        <AgentAvatar agentId={agentId} size={24} />
                        <span
                          className="text-[11px]"
                          style={{ color: meta.nameColor }}
                        >
                          {meta.label}
                        </span>
                      </div>
                    );
                  })}
                  {phase.key === "execute" &&
                    dynamicAgents.map((agent) => (
                      <div
                        key={agent.taskId}
                        className="flex items-center gap-1.5"
                      >
                        <div
                          className="w-6 h-6 rounded-full flex items-center justify-center text-white text-[10px] font-bold"
                          style={{ backgroundColor: agent.color }}
                        >
                          {agent.name[0]}
                        </div>
                        <span
                          className="text-[11px]"
                          style={{ color: agent.color }}
                        >
                          {agent.name}
                        </span>
                      </div>
                    ))}
                </div>
              </GlassCard>
            );
          })}
        </div>
      </div>

      {/* 任务信息 */}
      <div className="p-4">
        <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-3">
          任务信息
        </h3>
        <dl className="space-y-2 text-xs">
          <InfoRow
            label="状态"
            value={
              isRunning
                ? "运行中"
                : currentPhase
                  ? "已暂停"
                  : "未开始"
            }
          />
          <InfoRow
            label="当前阶段"
            value={
              currentPhase
                ? PHASE_PANELS.find((p) => p.key === currentPhase)?.label ??
                  currentPhase
                : "—"
            }
          />
          <InfoRow label="事件数" value={String(events.length)} />
        </dl>
      </div>
    </aside>
  );
}

function StatusDot({
  status,
}: {
  status: "pending" | "active" | "completed" | "error";
}) {
  const colors = {
    pending: "bg-text-disabled",
    active: "bg-status-warning animate-pulse-glow",
    completed: "bg-status-success",
    error: "bg-status-error",
  };
  return (
    <span className={`w-2 h-2 rounded-full shrink-0 ${colors[status]}`} />
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <dt className="text-text-muted">{label}</dt>
      <dd className="text-text-body font-medium">{value}</dd>
    </div>
  );
}
