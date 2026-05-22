# src/ui/unit_merge_dialog.py
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from src.managers.unit_manager import UnitManager


class UnitMergeDialog(QDialog):
    """Dialog for merging two units into one."""

    def __init__(
        self,
        manager: UnitManager,
        preselect: str | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._manager = manager
        self._names = [u.name for u in manager.get_all()]
        self._keep_choice: str | None = None
        self.setWindowTitle("合并单位")
        self.setMinimumWidth(400)
        self._setup_ui(preselect)

    def _make_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.addItems(self._names)
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        completer = QCompleter(self._names)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        combo.setCompleter(completer)
        return combo

    def _setup_ui(self, preselect: str | None):
        layout = QVBoxLayout(self)

        sel_group = QGroupBox("选择单位")
        sel_layout = QVBoxLayout(sel_group)

        row_a = QHBoxLayout()
        row_a.addWidget(QLabel("单位 A:"))
        self._combo_a = self._make_combo()
        row_a.addWidget(self._combo_a, 1)
        sel_layout.addLayout(row_a)

        row_b = QHBoxLayout()
        row_b.addWidget(QLabel("单位 B:"))
        self._combo_b = self._make_combo()
        row_b.addWidget(self._combo_b, 1)
        sel_layout.addLayout(row_b)

        layout.addWidget(sel_group)

        if preselect:
            idx = self._combo_a.findText(preselect)
            if idx >= 0:
                self._combo_a.setCurrentIndex(idx)

        keep_group = QGroupBox("保留标准名称")
        keep_layout = QVBoxLayout(keep_group)
        self._radio_a = QRadioButton()
        self._radio_b = QRadioButton()
        keep_layout.addWidget(self._radio_a)
        keep_layout.addWidget(self._radio_b)
        layout.addWidget(keep_group)

        preview_group = QGroupBox("合并预览")
        preview_layout = QVBoxLayout(preview_group)
        self._preview_aliases = QLabel("别名: —")
        self._preview_aliases.setWordWrap(True)
        preview_layout.addWidget(self._preview_aliases)
        layout.addWidget(preview_group)

        btn_row = QHBoxLayout()
        self._merge_btn = QPushButton("合并")
        self._merge_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(self._merge_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        self._combo_a.currentIndexChanged.connect(self._update_preview)
        self._combo_b.currentIndexChanged.connect(self._update_preview)
        self._radio_a.toggled.connect(self._update_preview)

        self._update_radio_labels()
        self._radio_a.setChecked(True)
        self._update_preview()

    def get_merge_params(self) -> tuple[str, str]:
        name_a = self._combo_a.currentText()
        name_b = self._combo_b.currentText()
        if self._radio_a.isChecked():
            return name_a, name_b
        return name_b, name_a

    def _update_radio_labels(self):
        name_a = self._combo_a.currentText() or "A"
        name_b = self._combo_b.currentText() or "B"
        self._radio_a.setText(f"保留: {name_a}")
        self._radio_b.setText(f"保留: {name_b}")

    def _update_preview(self):
        self._update_radio_labels()
        name_a = self._combo_a.currentText()
        name_b = self._combo_b.currentText()
        if not name_a or not name_b:
            return
        keep_name = name_a if self._radio_a.isChecked() else name_b
        remove_name = name_b if self._radio_a.isChecked() else name_a
        keep_unit = self._manager.get_by_name(keep_name)
        remove_unit = self._manager.get_by_name(remove_name)
        if keep_unit is None or remove_unit is None:
            return
        all_aliases = set(keep_unit.aliases) | set(remove_unit.aliases)
        all_aliases.discard(keep_unit.name)
        all_aliases.add(remove_name)
        for a in remove_unit.aliases:
            all_aliases.add(a)
        text = ", ".join(sorted(all_aliases)) if all_aliases else "(无)"
        self._preview_aliases.setText(f"别名: {text}")
        self._merge_btn.setEnabled(name_a != name_b)
