from __future__ import annotations

import time
from typing import Any

from agentloom.graph.state import AgentLoomState


def consultant(state: AgentLoomState) -> dict[str, Any]:
    """模拟 Consultant 阶段：分析任务需求。"""
    time.sleep(0.5)  # 模拟思考
    return {
        "phase": "consult",
        "consult_confidence": 0.92,
        "message": (
            "已完成需求分析。用户希望构建一个 **待办事项管理 API**，"
            "核心功能包括：\n"
            "- CRUD 操作（创建、读取、更新、删除）\n"
            "- 按优先级和截止日期排序\n"
            "- 标签分类系统\n\n"
            "置信度: **92%**，需求清晰度较高，可以进入架构设计阶段。"
        ),
    }


def architect(state: AgentLoomState) -> dict[str, Any]:
    """模拟 Architect 阶段：设计技术方案。"""
    time.sleep(0.8)
    return {
        "phase": "architect",
        "blueprint": {
            "steps": [
                "定义 Pydantic 数据模型 (TodoItem)",
                "实现 SQLite 持久化层",
                "构建 FastAPI CRUD 路由",
                "添加排序和过滤查询参数",
                "编写单元测试",
            ],
            "acceptance": [
                "所有 CRUD 端点返回正确状态码",
                "排序功能覆盖优先级和日期两个维度",
                "测试覆盖率 > 80%",
            ],
        },
        "architect_gap_notes": "",
        "message": (
            "技术方案设计完成：\n\n"
            "**技术栈**: FastAPI + SQLite + Pydantic v2\n\n"
            "**执行步骤** (5 步):\n"
            "1. 定义 `TodoItem` 数据模型\n"
            "2. 实现 SQLite 持久化层\n"
            "3. 构建 CRUD 路由\n"
            "4. 添加排序/过滤参数\n"
            "5. 编写单元测试\n\n"
            "**验收标准**: CRUD 状态码正确、双维度排序、测试覆盖 >80%\n\n"
            "请审核此方案后继续。"
        ),
    }


def hitl_blueprint(state: AgentLoomState) -> dict[str, Any]:
    """模拟 HITL 阶段：等待人工审核蓝图。"""
    return {
        "phase": "hitl_blueprint",
        "message": (
            "蓝图已提交审核。\n\n"
            "请确认以上 5 个执行步骤和 3 条验收标准是否符合预期。"
            "如需调整，请在对话中说明修改意见。"
        ),
    }


def experts(state: AgentLoomState) -> dict[str, Any]:
    """模拟 Expert Swarm 阶段：并行执行任务。"""
    time.sleep(1.0)
    return {
        "phase": "experts",
        "expert_runs": [
            {
                "expert": "data-modeler",
                "status": "done",
                "summary": "TodoItem 模型定义完成，包含 id/title/description/priority/due_date/tags/completed 字段",
            },
            {
                "expert": "backend-dev",
                "status": "done",
                "summary": "CRUD 路由实现完成: POST/GET/PUT/DELETE /api/todos，支持 ?sort_by=priority&order=desc 查询",
            },
            {
                "expert": "test-writer",
                "status": "done",
                "summary": "编写 12 个测试用例，覆盖率 87%，全部通过",
            },
        ],
        "message": (
            "Expert Swarm 执行完成，3 位专家并行工作：\n\n"
            "**data-modeler**: TodoItem 模型已定义 (7 字段)\n"
            "**backend-dev**: CRUD 路由已实现，含排序过滤\n"
            "**test-writer**: 12 个测试用例，覆盖率 87%\n\n"
            "全部任务成功完成，进入审查阶段。"
        ),
    }


def reviewer(state: AgentLoomState) -> dict[str, Any]:
    """模拟 Reviewer 阶段：审查交付物。"""
    time.sleep(0.5)
    r = int(state.get("review_round", 0))
    return {
        "phase": "review",
        "review_round": r + 1,
        "review_verdict": "pass",
        "message": (
            f"审查完成（第 {r + 1} 轮）：\n\n"
            "**结论: PASS** ✅\n\n"
            "- 数据模型设计合理，字段完整\n"
            "- API 路由符合 RESTful 规范\n"
            "- 测试覆盖率 87% 超过 80% 标准\n"
            "- 排序功能同时支持优先级和日期\n\n"
            "所有验收标准均已满足，任务完成。"
        ),
    }
