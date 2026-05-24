# src/ui/unit_panel.py
from __future__ import annotations

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.managers.file_manager import FileManager
from src.managers.unit_manager import UnitManager


class UnitPanel(QWidget):
    """Panel for managing cooking units (add, edit, merge, batch rename)."""

    unit_changed = Signal(str, str)  # emitted as (old_name, new_name) after batch rename
    units_updated = Signal()  # emitted when unit list changes
    navigate_to_recipe = Signal(str)  # emitted when user double-clicks a recipe reference

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._mgr: UnitManager | None = None
        self._fm: FileManager | None = None
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

        # Add unit button
        self._add_btn = QPushButton("新建单位")
        self._add_btn.clicked.connect(self._on_add)
        layout.addWidget(self._add_btn)

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
        self._split_btn = QPushButton("拆分别名...")
        self._split_btn.clicked.connect(self._on_split)
        btn_row.addWidget(self._save_btn)
        btn_row.addWidget(self._delete_btn)
        btn_row.addWidget(self._merge_btn)
        btn_row.addWidget(self._split_btn)
        detail_layout.addLayout(btn_row)

        # Reverse lookup: recipes using this unit
        self._ref_label = QLabel("引用菜谱:")
        self._ref_label.setStyleSheet("font-weight: bold; margin-top: 6px;")
        detail_layout.addWidget(self._ref_label)
        self._ref_list = QListWidget()
        self._ref_list.setMaximumHeight(120)
        self._ref_list.itemDoubleClicked.connect(self._on_ref_double_clicked)
        detail_layout.addWidget(self._ref_list)

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
        self._rename_from.setEditable(False)
        self._rename_to = QComboBox()
        self._rename_to.setEditable(False)
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

    def set_file_manager(self, fm: FileManager):
        """Set the file manager for reverse lookup."""
        self._fm = fm

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

        # Reverse lookup
        self._populate_ref_list(unit)

    def _on_field_changed(self, *_):
        self._save_btn.setEnabled(True)

    def _on_add(self):
        """Create a new unit."""
        if self._mgr is None:
            return
        name, ok = QInputDialog.getText(self, "新建单位", "单位名称:")
        if not ok or not name.strip():
            return
        name = name.strip()
        if self._mgr.get_by_name(name) is not None:
            QMessageBox.warning(self, "名称冲突", f"单位「{name}」已存在。")
            return
        self._mgr.add(name)
        self.units_updated.emit()
        self.refresh_list()
        # Select the newly added unit
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            unit = item.data(0, Qt.ItemDataRole.UserRole)
            if unit and unit.name == name:
                self._tree.setCurrentItem(item)
                break

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
        # Ask user to pick a replacement unit before deleting
        all_names = self._mgr.get_display_names()
        other_names = [n for n in all_names if n != name]
        if other_names:
            from PySide6.QtWidgets import QInputDialog
            replace_name, ok = QInputDialog.getItem(
                self, "选择替换单位",
                f"删除「{name}」后，请选择一个单位作为替代（选空则不替换）：",
                ["(无)"] + other_names,
                0,
                False,
            )
            if not ok:
                return
            if replace_name == "(无)":
                replace_name = ""
        else:
            replace_name = ""

        self._mgr.remove(self._selected_unit.key)
        if replace_name:
            self.unit_changed.emit(name, replace_name)
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

    def _on_split(self):
        """Split selected aliases of the current unit into standalone units."""
        if self._mgr is None or self._selected_unit is None:
            return
        unit = self._selected_unit
        if not unit.aliases:
            QMessageBox.information(self, "拆分别名", f"「{unit.name}」没有可拆分的别名。")
            return

        # Build a dialog with checkboxes for each alias
        dlg = _SplitAliasDialog(unit.aliases, unit.name, parent=self)
        if not dlg.exec():
            return
        to_split = dlg.get_selected_aliases()
        if not to_split:
            return

        # For each selected alias, create a new standalone unit
        for alias_name in to_split:
            self._mgr.add(alias_name, [alias_name])

        # Remove the selected aliases from the original unit
        remaining_aliases = [a for a in unit.aliases if a not in to_split]
        self._mgr.update(key=unit.key, aliases=remaining_aliases)

        self._selected_unit = None
        self._detail_frame.setVisible(False)
        self.units_updated.emit()
        self.refresh_list()

    # ------------------------------------------------------------------
    # Reverse lookup
    # ------------------------------------------------------------------

    def _populate_ref_list(self, unit):
        """Fill the reference list with recipes using this unit."""
        self._ref_list.clear()
        names = {unit.name} | set(unit.aliases)
        recipes = self._find_recipes_using_unit(names)
        self._ref_label.setText(f"引用菜谱 ({len(recipes)}):")
        for recipe_name in recipes:
            item = QListWidgetItem(recipe_name)
            item.setData(Qt.ItemDataRole.UserRole, f"{recipe_name}.json")
            self._ref_list.addItem(item)

    def _find_recipes_using_unit(self, names: set[str]) -> list[str]:
        """Scan all output JSON files for recipes using any of the given unit names."""
        if self._fm is None:
            return []
        recipes: list[str] = []
        for path in self._fm.list_output_recipes():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for ing in data.get("ingredients", []):
                    if ing.get("unit", "") in names:
                        recipes.append(path.stem)
                        break
            except Exception:
                pass
        return sorted(recipes)

    def _on_ref_double_clicked(self, item: QListWidgetItem):
        """Navigate to the referenced recipe."""
        rel_path = item.data(Qt.ItemDataRole.UserRole)
        if rel_path:
            self.navigate_to_recipe.emit(rel_path)


class _SplitAliasDialog(QMessageBox):
    """Dialog to select which aliases to split into standalone units."""

    def __init__(self, aliases: list[str], unit_name: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("拆分别名")
        self.setText(f"选择要从「{unit_name}」中拆出的别名：")
        self.setIcon(QMessageBox.Icon.Question)
        self.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )

        # Build checkbox list
        self._checkboxes: list[QCheckBox] = []
        for alias in sorted(aliases):
            cb = QCheckBox(alias)
            cb.setChecked(True)  # default all selected
            self._checkboxes.append(cb)

        layout = self.layout()
        if layout:
            container = QWidget()
            v = QVBoxLayout(container)
            for cb in self._checkboxes:
                v.addWidget(cb)
            v.addStretch()
            # Find where to insert in QMessageBox layout
            # QMessageBox uses a QGridLayout; insert after the label
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and isinstance(item.widget(), QLabel):
                    # Insert after the text label
                    row = layout.getItemPosition(i)[0]
                    layout.addWidget(container, row + 1, 0, 1, layout.columnCount())
                    break

    def get_selected_aliases(self) -> list[str]:
        return [cb.text() for cb in self._checkboxes if cb.isChecked()]
