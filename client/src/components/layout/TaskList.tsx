import { useEffect, useState } from "react";
import { Search, Plus } from "lucide-react";
import { useTaskStore } from "../../stores/taskStore";

export function TaskList() {
  const { tasks, activeTaskId, loading, fetchTasks, createTask, setActiveTask } =
    useTaskStore();
  const [search, setSearch] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [newName, setNewName] = useState("");

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  const filtered = search
    ? tasks.filter((t) => t.name.toLowerCase().includes(search.toLowerCase()))
    : tasks;

  const handleCreate = async () => {
    if (!newName.trim()) return;
    await createTask(newName.trim());
    setNewName("");
    setIsCreating(false);
  };

  return (
    <aside className="w-60 shrink-0 flex flex-col border-r border-border-subtle bg-bg-surface/50">
      {/* 搜索框 */}
      <div className="p-3 pb-2">
        <div className="glass flex items-center gap-2 px-3 py-2 text-sm">
          <Search size={14} className="text-text-muted shrink-0" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索项目组..."
            className="bg-transparent outline-none text-text-primary placeholder:text-text-disabled flex-1 min-w-0"
          />
        </div>
      </div>

      {/* 新建任务 */}
      <div className="px-3 pb-2">
        {isCreating ? (
          <div className="glass p-2 space-y-2">
            <input
              autoFocus
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreate();
                if (e.key === "Escape") setIsCreating(false);
              }}
              placeholder="项目组名称..."
              className="w-full bg-transparent outline-none text-sm text-text-primary placeholder:text-text-disabled"
            />
            <div className="flex gap-2">
              <button
                onClick={handleCreate}
                className="flex-1 text-xs py-1 rounded-md gradient-brand text-white"
              >
                创建
              </button>
              <button
                onClick={() => setIsCreating(false)}
                className="flex-1 text-xs py-1 rounded-md glass text-text-secondary"
              >
                取消
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setIsCreating(true)}
            className="w-full flex items-center justify-center gap-1.5 py-2 text-sm rounded-[var(--radius-card)] gradient-brand-border text-text-secondary hover:text-text-primary transition-colors"
          >
            <Plus size={14} />
            新建项目组
          </button>
        )}
      </div>

      {/* 任务列表 */}
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {loading && (
          <p className="text-center text-text-muted text-xs py-4">加载中...</p>
        )}
        {filtered.map((task) => {
          const isActive = task.id === activeTaskId;
          return (
            <button
              key={task.id}
              onClick={() => setActiveTask(task.id)}
              className={`
                w-full text-left px-3 py-2.5 rounded-lg mb-1 transition-all duration-150
                ${isActive
                  ? "bg-brand-purple/15 border border-brand-purple/20"
                  : "hover:bg-bg-hover border border-transparent"
                }
              `}
            >
              <div className="flex items-center gap-2">
                <span
                  className={`w-2 h-2 rounded-full shrink-0 ${
                    isActive ? "bg-status-info" : "border border-text-disabled"
                  }`}
                />
                <span className="text-sm text-text-primary truncate">
                  {task.name}
                </span>
              </div>
              <p className="text-[11px] text-text-muted mt-1 ml-4 truncate">
                {new Date(task.modified_at).toLocaleString("zh-CN", {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </p>
            </button>
          );
        })}
        {!loading && filtered.length === 0 && (
          <p className="text-center text-text-muted text-xs py-8">
            {search ? "无匹配任务" : "暂无任务"}
          </p>
        )}
      </div>
    </aside>
  );
}
