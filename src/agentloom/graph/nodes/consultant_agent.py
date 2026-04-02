from __future__ import annotations

import json
import re

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from agentloom.llm.factory import get_chat_model

CONSULTANT_SYSTEM_PROMPT = """\
你是一位活泼、专业的需求分析师，正在项目群聊中和用户沟通需求。

## 你的工作方式
1. 用户会先自由描述需求，你仔细分析后从以下维度检查是否有遗漏：
   - 核心目标（要做什么）
   - 约束条件（技术栈、平台、时间限制）
   - 成功标准（怎样算完成）
   - 优先级（哪些必须有，哪些可选）
2. 每次只问一个问题，优先用选择题格式
3. 语气活泼友好，像在工作群里和同事聊天，正事说完可以偶尔加点打趣的话
4. 不要使用 Markdown 标题格式，用群聊对话风格

## 判断需求是否充分
当你认为收集到的信息足够支撑架构设计时，输出一个结构化的需求摘要，格式如下：

```requirement_summary
{
  "project_name": "项目名称",
  "core_goal": "核心目标描述",
  "constraints": {
    "tech_stack": ["技术1", "技术2"],
    "platform": "web/cli/mobile 或 null",
    "timeline": "时间限制 或 null"
  },
  "success_criteria": ["标准1", "标准2"],
  "features": [
    {"name": "功能名", "description": "功能描述", "priority": "must/should/nice_to_have"}
  ],
  "additional_notes": "其他备注 或 null",
  "raw_conversation_summary": "用一段话总结整个需求"
}
```

输出摘要后，跟用户说"确认没问题的话点击启动项目，有需要调整的地方直接告诉我~"

## 重要规则
- 在信息不够充分之前，绝对不要输出 requirement_summary 块
- 不要一次问多个问题，一次只问一个
- 如果用户的描述已经很完整，可以只确认1-2个关键点就给出摘要\
"""

_SUMMARY_PATTERN = re.compile(
    r"```requirement_summary\s*\n(.*?)\n```",
    re.DOTALL,
)


def strip_summary_block(text: str, summary: dict | None = None) -> str:
    """从 LLM 回复中剥离 requirement_summary JSON 块，替换为友好的格式化摘要。"""
    # 去掉 JSON 代码块
    clean = _SUMMARY_PATTERN.sub("", text).strip()

    if summary:
        # 用友好格式展示摘要
        lines = ["\n📋 **需求摘要**\n"]
        if summary.get("project_name"):
            lines.append(f"**项目名称：** {summary['project_name']}")
        if summary.get("core_goal"):
            lines.append(f"**核心目标：** {summary['core_goal']}")
        constraints = summary.get("constraints", {})
        if constraints.get("tech_stack"):
            lines.append(f"**技术栈：** {', '.join(constraints['tech_stack'])}")
        if constraints.get("platform"):
            lines.append(f"**平台：** {constraints['platform']}")
        if constraints.get("timeline"):
            lines.append(f"**时间要求：** {constraints['timeline']}")
        criteria = summary.get("success_criteria", [])
        if criteria:
            lines.append("**成功标准：**")
            for c in criteria:
                lines.append(f"  - {c}")
        features = summary.get("features", [])
        if features:
            lines.append("**功能点：**")
            for f in features:
                priority_map = {"must": "必须", "should": "应该", "nice_to_have": "可选"}
                p = priority_map.get(f.get("priority", ""), f.get("priority", ""))
                lines.append(f"  - {f.get('name', '?')}（{p}）: {f.get('description', '')}")
        if summary.get("additional_notes"):
            lines.append(f"**备注：** {summary['additional_notes']}")

        clean = clean + "\n" + "\n".join(lines) if clean else "\n".join(lines)

    return clean


def build_initial_greeting() -> str:
    """返回 Consultant 的开场白。"""
    return (
        "Hey~ 我是这个项目组的需求分析师，负责帮你把想法梳理清楚 \U0001F4CB\n\n"
        "跟我聊聊你想做什么吧！随便说就行，一句话也OK，"
        "我会根据你说的做一些追问来确保我们理解一致~"
    )


def _parse_summary(text: str) -> dict | None:
    """从 LLM 回复中解析 requirement_summary JSON 块。"""
    m = _SUMMARY_PATTERN.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except (json.JSONDecodeError, ValueError):
        return None


def consult_turn(history: list[BaseMessage]) -> tuple[str, bool, dict | None]:
    """执行一轮 Consultant 对话。

    返回 (回复文本, 是否就绪, 解析的摘要或None)。
    """
    llm = get_chat_model()
    resp = llm.invoke(history)
    text = resp.content

    summary = _parse_summary(text)
    is_ready = summary is not None

    return text, is_ready, summary


def extract_requirement(history: list[BaseMessage]) -> dict:
    """从对话历史中提取结构化需求。

    如果最后一条 AI 消息已包含 summary 块则直接用，否则做一次额外 LLM 调用。
    """
    for msg in reversed(history):
        if isinstance(msg, AIMessage) and "requirement_summary" in msg.content:
            summary = _parse_summary(msg.content)
            if summary:
                return summary

    extraction_prompt = (
        "请根据上面的对话，输出结构化的需求摘要。"
        "必须严格使用 ```requirement_summary\\n{...}\\n``` 格式输出 JSON。"
    )
    llm = get_chat_model()
    resp = llm.invoke(history + [HumanMessage(content=extraction_prompt)])
    summary = _parse_summary(resp.content)

    if summary:
        return summary

    return {
        "project_name": "未命名项目",
        "core_goal": history[-1].content if history else "未收集到需求",
        "constraints": {"tech_stack": [], "platform": None, "timeline": None},
        "success_criteria": [],
        "features": [],
        "additional_notes": None,
        "raw_conversation_summary": resp.content,
    }
