from agentloom.graph.nodes.architect_agent import format_blueprint_message


SAMPLE_BLUEPRINT = {
    "tasks": [
        {
            "id": "t1",
            "name": "初始化项目",
            "goal": "搭建基础目录",
            "tools": ["shell"],
            "depends_on": [],
        },
        {
            "id": "t2",
            "name": "实现核心逻辑",
            "goal": "编写主要代码",
            "tools": ["python"],
            "depends_on": ["t1"],
        },
    ]
}

LLM_TEXT = (
    "```blueprint\n"
    '{"tasks": []}\n'
    "```\n\n"
    "方案出炉！共 2 个任务，大家看看有没有问题~"
)


def test_strips_blueprint_block():
    result = format_blueprint_message(LLM_TEXT, SAMPLE_BLUEPRINT)
    assert "```blueprint" not in result
    assert "```" not in result


def test_contains_task_names():
    result = format_blueprint_message(LLM_TEXT, SAMPLE_BLUEPRINT)
    assert "初始化项目" in result
    assert "实现核心逻辑" in result


def test_contains_dependency():
    result = format_blueprint_message(LLM_TEXT, SAMPLE_BLUEPRINT)
    # t2 依赖 t1，t1 的名称「初始化项目」应出现在依赖说明里
    assert "初始化项目" in result


def test_contains_llm_summary():
    result = format_blueprint_message(LLM_TEXT, SAMPLE_BLUEPRINT)
    assert "方案出炉" in result


def test_empty_blueprint_returns_clean_text():
    result = format_blueprint_message("纯文本，无代码块", None)
    assert result == "纯文本，无代码块"


def test_no_tasks_blueprint():
    result = format_blueprint_message(LLM_TEXT, {"tasks": []})
    # 没有任务时直接返回剥离后的 LLM 文本
    assert "方案出炉！共 2 个任务" in result
    assert "```blueprint" not in result
