# src/ui/settings_dialog.py
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QWidget,
)


CONFIG_DIR = Path.home() / ".howtocook_organizer"
CONFIG_FILE = CONFIG_DIR / "config.json"


class SettingsDialog(QDialog):
    """Dialog for configuring source/output repo paths."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(520)

        # --- form layout ---
        form = QFormLayout(self)

        # Source repo row
        source_row = QHBoxLayout()
        self._source_edit = QLineEdit()
        self._source_edit.setPlaceholderText("HowToCook 源仓库路径")
        source_btn = QPushButton("浏览...")
        source_btn.clicked.connect(self._browse_source)
        source_row.addWidget(self._source_edit, 1)
        source_row.addWidget(source_btn)
        form.addRow("源仓库路径 (HowToCook):", source_row)

        # Output repo row
        output_row = QHBoxLayout()
        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("HowToCook_json 输出仓库路径")
        output_btn = QPushButton("浏览...")
        output_btn.clicked.connect(self._browse_output)
        output_row.addWidget(self._output_edit, 1)
        output_row.addWidget(output_btn)
        form.addRow("输出仓库路径 (HowToCook_json):", output_row)

        # Buttons
        btn_row = QHBoxLayout()
        save_btn = QPushButton("保存")
        cancel_btn = QPushButton("取消")
        save_btn.clicked.connect(self._on_save)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        form.addRow(btn_row)

    # ------------------------------------------------------------------
    # Public helpers (static)
    # ------------------------------------------------------------------

    @staticmethod
    def load_config() -> dict:
        """Load config from disk. Returns empty dict if not found."""
        if not CONFIG_FILE.exists():
            return {}
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    @staticmethod
    def save_config(config: dict) -> None:
        """Persist *config* dict to the config file."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def validate_paths(config: dict) -> tuple[bool, str]:
        """Check whether source_dir and output_dir in *config* are valid.

        Returns (ok, error_message).
        """
        source = config.get("source_dir", "")
        output = config.get("output_dir", "")
        if not source or not output:
            return False, "请设置源仓库路径和输出仓库路径。"
        if not Path(source).is_dir():
            return False, f"源仓库路径无效: {source}"
        if not Path(output).is_dir():
            return False, f"输出仓库路径无效: {output}"
        return True, ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_config(self) -> dict:
        """Return current dialog values as a config dict."""
        return {
            "source_dir": self._source_edit.text().strip(),
            "output_dir": self._output_edit.text().strip(),
        }

    def set_config(self, config: dict) -> None:
        """Populate dialog fields from *config*."""
        self._source_edit.setText(config.get("source_dir", ""))
        self._output_edit.setText(config.get("output_dir", ""))

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _browse_source(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择 HowToCook 源仓库")
        if path:
            self._source_edit.setText(path)

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择 HowToCook_json 输出仓库")
        if path:
            self._output_edit.setText(path)

    def _on_save(self) -> None:
        config = self.get_config()
        ok, msg = self.validate_paths(config)
        if not ok:
            QMessageBox.warning(self, "路径无效", msg)
            return
        self.save_config(config)
        self.accept()
