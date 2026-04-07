from __future__ import annotations

import json
import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from agentloom.config.loader import load_all
from agentloom.llm.factory import get_chat_model
from agentloom.skills.registry import merged_skills_for_agents
from agentloom.tasks.requirement import load_requirement

ARCHITECT_SYSTEM_PROMPT = """\
你是一位经验丰富的架构设计师，正在项目群聊中做技术方案设计。

## 你的职责
根据需求分析师整理的需求文档和当前可用的工具，设计一个可执行的任务规划（DAG）。

## 你收到的信息
1. 结构化需求文档（JSON）
2. 当前可用工具清单（skills、MCP 服务、内置能力）

## 输出要求
你必须输出一个 JSON 格式的任务规划，用 ```blueprint``` 代码块包裹：

```blueprint
{
  "tasks": [
    {
      "id": "t1",
      "name": "任务名称",
      "goal": "这个任务要达成什么目标",
      "acceptance_criteria": ["验收标准1", "验收标准2"],
      "tools": ["tool_id_1", "tool_id_2"],
      "depends_on": []
    },
    {
      "id": "t2",
      "name": "另一个任务",
      "goal": "目标描述",
      "acceptance_criteria": ["验收标准"],
      "tools": ["tool_id"],
      "depends_on": ["t1"]
    }
  ]
}
```

## 规则
- 每个任务的 tools 只能使用可用工具清单中的工具 ID 或内置能力（shell、python）
- 任务之间的 depends_on 要合理，体现真实的依赖关系
- 没有依赖的任务可以并行执行
- 任务粒度适中，不要太大也不要太碎
- 输出 blueprint 块后，用活泼的语气说一句总结，比如"方案出炉！一共X个任务，预计执行顺序是...大家看看有没有问题~"
- 语气活泼，像在工作群里跟同事汇报方案一样
- 不要使用 Markdown 标题格式
"""

_BLUEPRINT_PATTERN = re.compile(
    r"```blueprint\s*\n(.*?)\n```",
    re.DOTALL,
)


def _gather_available_tools(task_path: Path | None = None) -> str:
    """收集当前可用的工具清单，返回格式化的文本描述。"""
    lines = ["## 可用工具清单\n"]

    # 内置能力
    lines.append("### 内置能力")
    lines.append("- shell: 执行命令行操作")
    lines.append("- python: 运行 Python 脚本（workspace 内有独立 venv）")
    lines.append("")

    # Skills
    try:
        skills = merged_skills_for_agents(task_workspace=task_path)
        if skills:
            lines.append("### 已安装 Skills")
            for s in skills:
                if s.enabled:
                    desc = s.description or "无描述"
                    lines.append(f"- {s.id}: {s.name or s.id} — {desc}")
            lines.append("")
    except Exception:
        pass

    # MCPs
    try:
        cfg = load_all()
        if cfg.mcps:
            lines.append("### 已配置 MCP 服务")
            for m in cfg.mcps:
                lines.append(f"- {m.id}: {m.name or m.id}")
            lines.append("")
    except Exception:
        pass

    return "\n".join(lines)


def _parse_blueprint(text: str) -> dict | None:
    """从 LLM 回复中解析 blueprint JSON 块。"""
    m = _BLUEPRINT_PATTERN.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except (json.JSONDecodeError, ValueError):
        return None


def generate_blueprint(
    requirement: dict,
    task_path: Path | None = None,
) -> tuple[str, dict | None]:
    """根据需求和可用工具生成架构规划。

    返回 (LLM完整回复文本, 解析出的blueprint字典或None)。
    """
    tools_text = _gather_available_tools(task_path)

    req_text = json.dumps(requirement, ensure_ascii=False, indent=2)

    user_prompt = (
        f"以下是需求文档：\n```json\n{req_text}\n```\n\n"
        f"{tools_text}\n\n"
        "请根据需求和可用工具，设计任务规划（DAG），用 ```blueprint``` 格式输出。"
    )

    llm = get_chat_model()
    resp = llm.invoke([
        SystemMessage(content=ARCHITECT_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ])
    text = resp.content

    blueprint = _parse_blueprint(text)
    return text, blueprint


def format_blueprint_message(text: str, blueprint: dict | None) -> str:
    """将架构师 LLM 回复转为可读群聊消息。

    剥离 ```blueprint 代码块，用 blueprint dict 生成人类可读任务清单。
    若 blueprint 为空则直接返回剥离代码块后的文本。
    """
    import re as _re

    # 剥离 ```blueprint ... ``` 块
    clean = _BLUEPRINT_PATTERN.sub("", text).strip()
    # 清理多余空行
    clean = _re.sub(r"\n{3,}", "\n\n", clean).strip()

    if not blueprint or not blueprint.get("tasks"):
        return clean or text

    tasks = blueprint["tasks"]
    task_map = {t["id"]: t.get("name", t["id"]) for t in tasks}

    lines = [f"方案出炉！一共 {len(tasks)} 个任务，按顺序推进 👇\n"]

    for t in tasks:
        name = t.get("name", t.get("id", "?"))
        goal = t.get("goal", "")
        tools = t.get("tools", [])
        deps = t.get("depends_on", [])
        dep_names = [task_map.get(d, d) for d in deps]

        header = f"📌 **{name}**"
        if dep_names:
            header += f"（依赖：{'、'.join(dep_names)}）"
        lines.append(header)
        if goal:
            lines.append(f"目标：{goal}")
        if tools:
            lines.append(f"工具：{', '.join(tools)}")
        lines.append("")

    # 追加 LLM 的活泼总结语（如果有）
    if clean:
        lines.append(clean)

    return "\n".join(lines).strip()
