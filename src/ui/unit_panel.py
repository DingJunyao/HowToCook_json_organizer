# src/ui/unit_panel.py
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.managers.unit_manager import UnitManager


class UnitPanel(QWidget):
    """Panel for managing cooking units (add, edit, merge, batch rename)."""

    unit_changed = Signal(str, str)  # emitted as (old_name, new_name) after batch rename
    units_updated = Signal()  # emitted when unit list changes

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._mgr: UnitManager | None = None
        self._selected_unit = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Title
        title = QLabel("单位库")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        # Search
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("搜索单位...")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._on_search)
        layout.addWidget(self._search_edit)

        # Tree
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(16)
        self._tree.setAnimated(True)
        self._tree.currentItemChanged.connect(self._on_item_changed)
        layout.addWidget(self._tree, stretch=1)

        # Editable detail area
        self._detail_frame = QFrame()
        self._detail_frame.setFrameShape(QFrame.StyledPanel)
        self._detail_frame.setVisible(False)
        detail_layout = QVBoxLayout(self._detail_frame)
        detail_layout.setContentsMargins(6, 6, 6, 6)

        self._detail_title = QLabel()
        self._detail_title.setStyleSheet("font-weight: bold; font-size: 13px;")
        detail_layout.addWidget(self._detail_title)

        # Name
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("名称:"))
        self._name_edit = QLineEdit()
        self._name_edit.textChanged.connect(self._on_field_changed)
        name_row.addWidget(self._name_edit, 1)
        detail_layout.addLayout(name_row)

        # Aliases
        alias_row = QHBoxLayout()
        alias_row.addWidget(QLabel("别名:"))
        self._alias_edit = QLineEdit()
        self._alias_edit.setPlaceholderText("多个别名用逗号分隔")
        self._alias_edit.textChanged.connect(self._on_field_changed)
        alias_row.addWidget(self._alias_edit, 1)
        detail_layout.addLayout(alias_row)

        # Action buttons
        btn_row = QHBoxLayout()
        self._save_btn = QPushButton("保存修改")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)
        self._delete_btn = QPushButton("删除")
        self._delete_btn.clicked.connect(self._on_delete)
        self._merge_btn = QPushButton("合并...")
        self._merge_btn.clicked.connect(self._on_merge)
        btn_row.addWidget(self._save_btn)
        btn_row.addWidget(self._delete_btn)
        btn_row.addWidget(self._merge_btn)
        detail_layout.addLayout(btn_row)

        layout.addWidget(self._detail_frame)

        # Batch rename section
        batch_frame = QFrame()
        batch_frame.setFrameShape(QFrame.StyledPanel)
        batch_layout = QVBoxLayout(batch_frame)
        batch_layout.setContentsMargins(6, 6, 6, 6)

        batch_label = QLabel("批量替换")
        batch_label.setStyleSheet("font-weight: bold;")
        batch_layout.addWidget(batch_label)

        rename_row = QHBoxLayout()
        self._rename_from = QComboBox()
        self._rename_from.setEditable(True)
        self._rename_to = QComboBox()
        self._rename_to.setEditable(True)
        self._rename_btn = QPushButton("替换")
        self._rename_btn.clicked.connect(self._on_batch_rename)
        rename_row.addWidget(QLabel("从:"))
        rename_row.addWidget(self._rename_from, 1)
        rename_row.addWidget(QLabel("到:"))
        rename_row.addWidget(self._rename_to, 1)
        rename_row.addWidget(self._rename_btn)
        batch_layout.addLayout(rename_row)

        layout.addWidget(batch_frame)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_unit_manager(self, mgr: UnitManager):
        self._mgr = mgr
        self.refresh_list()

    def refresh_list(self):
        self._tree.clear()
        if self._mgr is None:
            return

        query = self._search_edit.text().strip().lower()
        units = self._mgr.get_all()
        if query:
            units = [u for u in units if query in u.name.lower()
                     or any(query in a.lower() for a in u.aliases)]

        for unit in sorted(units, key=lambda u: u.name):
            aliases_text = f" ({', '.join(unit.aliases)})" if unit.aliases else ""
            item = QTreeWidgetItem(self._tree, [f"{unit.name}{aliases_text}"])
            item.setData(0, Qt.ItemDataRole.UserRole, unit)

        self._detail_frame.setVisible(False)
        self._selected_unit = None
        self._populate_rename_combos()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _populate_rename_combos(self):
        names = self._mgr.get_display_names() if self._mgr else []
        self._rename_from.clear()
        self._rename_from.addItems(names)
        self._rename_to.clear()
        self._rename_to.addItems(names)

    def _on_search(self, _text):
        self.refresh_list()

    def _on_item_changed(self, current: QTreeWidgetItem | None, _prev):
        if current is None:
            self._detail_frame.setVisible(False)
            self._selected_unit = None
            return
        unit = current.data(0, Qt.ItemDataRole.UserRole)
        if unit is None:
            self._detail_frame.setVisible(False)
            self._selected_unit = None
            return
        self._selected_unit = unit
        self._populate_detail(unit)
        self._detail_frame.setVisible(True)

    def _populate_detail(self, unit):
        self._name_edit.blockSignals(True)
        self._alias_edit.blockSignals(True)
        self._detail_title.setText(unit.name)
        self._name_edit.setText(unit.name)
        self._alias_edit.setText(", ".join(unit.aliases))
        self._save_btn.setEnabled(False)
        self._name_edit.blockSignals(False)
        self._alias_edit.blockSignals(False)

    def _on_field_changed(self, *_):
        self._save_btn.setEnabled(True)

    def _on_save(self):
        if self._mgr is None or self._selected_unit is None:
            return
        new_name = self._name_edit.text().strip()
        if not new_name:
            QMessageBox.warning(self, "无效输入", "单位名称不能为空。")
            return
        existing = self._mgr.get_by_name(new_name)
        if existing is not None and existing.key != self._selected_unit.key:
            QMessageBox.warning(self, "名称冲突",
                                f"已存在名为「{new_name}」的单位，请使用合并功能。")
            return
        old_name = self._selected_unit.name
        alias_text = self._alias_edit.text().strip()
        aliases = [a.strip() for a in alias_text.split(",") if a.strip()] if alias_text else []
        self._mgr.update(
            key=self._selected_unit.key,
            name=new_name,
            aliases=aliases,
        )
        self._save_btn.setEnabled(False)
        self.units_updated.emit()
        if old_name != new_name:
            self.unit_changed.emit(old_name, new_name)
        self.refresh_list()

    def _on_delete(self):
        if self._mgr is None or self._selected_unit is None:
            return
        name = self._selected_unit.name
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除单位「{name}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._mgr.remove(self._selected_unit.key)
        self._selected_unit = None
        self._detail_frame.setVisible(False)
        self.units_updated.emit()
        self.refresh_list()

    def _on_merge(self):
        if self._mgr is None or self._selected_unit is None:
            return
        from src.ui.unit_merge_dialog import UnitMergeDialog
        dlg = UnitMergeDialog(self._mgr, preselect=self._selected_unit.name, parent=self)
        if dlg.exec():
            keep_name, remove_name = dlg.get_merge_params()
            old_name = remove_name
            self._mgr.merge(keep_name, remove_name)
            self.unit_changed.emit(old_name, keep_name)
            self._selected_unit = None
            self._detail_frame.setVisible(False)
            self.units_updated.emit()
            self.refresh_list()

    def _on_batch_rename(self):
        if self._mgr is None:
            return
        old_name = self._rename_from.currentText().strip()
        new_name = self._rename_to.currentText().strip()
        if not old_name or not new_name:
            return
        if old_name == new_name:
            return
        reply = QMessageBox.question(
            self, "确认批量替换",
            f"将当前菜谱中所有「{old_name}」替换为「{new_name}」？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.unit_changed.emit(old_name, new_name)
