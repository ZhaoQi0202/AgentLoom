from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSplitter, QVBoxLayout, QWidget

from agentloom.paths import install_root
from agentloom.ui.dialogs.mcp_editor import McpEditorDialog
from agentloom.ui.panels.activity_panel import ActivityPanel
from agentloom.ui.panels.chat_panel import ChatPanel
from agentloom.ui.panels.task_list import TaskListPanel
from agentloom.ui.worker import GraphRunner


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"AgentLoom — {install_root()}")
        root = install_root()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self._btn_run_graph = QPushButton("运行图谱")
        self._btn_continue = QPushButton("继续")
        self._btn_continue.setEnabled(False)
        self._btn_add_mcp = QPushButton("添加 MCP")
        bar.addWidget(self._btn_run_graph)
        bar.addWidget(self._btn_continue)
        bar.addWidget(self._btn_add_mcp)
        outer.addLayout(bar)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._task_list = TaskListPanel()
        self._chat = ChatPanel()
        self._activity = ActivityPanel()
        splitter.addWidget(self._task_list)
        splitter.addWidget(self._chat)
        splitter.addWidget(self._activity)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 1)
        outer.addWidget(splitter)
        self._chat.message_sent.connect(self._activity.append_line)

        self._graph_thread = QThread()
        self._graph_runner = GraphRunner(install_root=root)
        self._graph_runner.moveToThread(self._graph_thread)
        self._graph_runner.phase_event.connect(self._on_graph_phase)
        self._graph_runner.interrupted.connect(self._on_graph_interrupted)
        self._graph_runner.finished.connect(self._on_graph_finished)
        self._graph_runner.error.connect(self._on_graph_error)
        self._btn_run_graph.clicked.connect(self._on_run_graph_clicked)
        self._btn_continue.clicked.connect(self._on_continue_clicked)
        self._btn_add_mcp.clicked.connect(self._on_add_mcp_clicked)
        self._graph_thread.start()

    def _on_graph_phase(self, node: str, payload: dict) -> None:
        phase = payload.get("phase", "")
        self._activity.append_line(f"[{node}] {phase}")

    def _on_graph_interrupted(self, next_node: str) -> None:
        self._activity.append_line(f"中断，待续: {next_node}")
        self._btn_continue.setEnabled(True)

    def _on_graph_finished(self) -> None:
        self._activity.append_line("图谱结束")
        self._btn_continue.setEnabled(False)

    def _on_graph_error(self, message: str) -> None:
        self._activity.append_line(f"错误: {message}")
        self._btn_continue.setEnabled(False)

    def _on_run_graph_clicked(self) -> None:
        self._btn_continue.setEnabled(False)
        self._activity.append_line("启动图谱…")
        self._graph_runner.request_start()

    def _on_continue_clicked(self) -> None:
        self._btn_continue.setEnabled(False)
        self._activity.append_line("继续…")
        self._graph_runner.request_resume()

    def _on_add_mcp_clicked(self) -> None:
        dlg = McpEditorDialog(config_root=root, parent=self)
        dlg.exec()
