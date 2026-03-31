import json
from pathlib import Path

from pydantic import ValidationError
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from agentloom.config.loader import ConfigValidationError, save_mcp_entry
from agentloom.config.models import McpEntry
from agentloom.paths import install_root


class McpEditorDialog(QDialog):
    def __init__(self, config_root: Path | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config_root = install_root() if config_root is None else config_root
        self.setWindowTitle("添加 MCP")
        self._id = QLineEdit(self)
        self._command = QLineEdit(self)
        self._args = QPlainTextEdit(self)
        self._args.setPlaceholderText('[] 或 ["-y", "pkg"]')
        self._args.setMaximumBlockCount(50)
        self._description = QLineEdit(self)
        form = QFormLayout()
        form.addRow("ID", self._id)
        form.addRow("命令", self._command)
        form.addRow("参数 (JSON 数组)", self._args)
        form.addRow("说明", self._description)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        outer = QVBoxLayout(self)
        outer.addLayout(form)
        outer.addWidget(buttons)

    def _on_save(self) -> None:
        raw_id = self._id.text().strip()
        if not raw_id:
            QMessageBox.warning(self, "校验失败", "ID 不能为空")
            return
        args_text = self._args.toPlainText().strip()
        if not args_text:
            args_list: list[str] = []
        else:
            try:
                parsed = json.loads(args_text)
            except json.JSONDecodeError as e:
                QMessageBox.warning(self, "校验失败", f"参数 JSON 无效: {e}")
                return
            if not isinstance(parsed, list):
                QMessageBox.warning(self, "校验失败", "参数必须是 JSON 数组")
                return
            if not all(isinstance(x, str) for x in parsed):
                QMessageBox.warning(self, "校验失败", "参数数组元素须为字符串")
                return
            args_list = list(parsed)
        cmd = self._command.text().strip() or None
        desc = self._description.text().strip() or None
        try:
            entry = McpEntry(id=raw_id, command=cmd, args=args_list, name=desc)
        except ValidationError as e:
            QMessageBox.warning(self, "校验失败", str(e))
            return
        try:
            save_mcp_entry(entry, self._config_root)
        except ConfigValidationError as e:
            QMessageBox.warning(self, "保存失败", str(e))
            return
        self.accept()
