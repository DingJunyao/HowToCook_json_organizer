# src/ui/ingredient_panel.py
from __future__ import annotations

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.managers.file_manager import FileManager
from src.managers.ingredient_manager import IngredientManager

CATEGORIES = ["蔬菜", "肉类", "水产", "禽蛋", "豆制品", "主食/谷物", "调料", "饮品", "干货", "其他"]


class IngredientPanel(QWidget):
    """Right-panel ingredient library reference for RecipeTab."""

    ingredient_changed = Signal()  # emitted when ingredients are modified
    navigate_to_recipe = Signal(str)  # emitted when user double-clicks a recipe reference

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._mgr: IngredientManager | None = None
        self._fm: FileManager | None = None
        self._selected_ingredient = None  # currently selected Ingredient object
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Title
        title = QLabel("食材库参考")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        # Search bar
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("搜索食材名称或别名...")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._on_search)
        layout.addWidget(self._search_edit)

        # Tree widget for ingredients grouped by category
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

        # Category
        cat_row = QHBoxLayout()
        cat_row.addWidget(QLabel("分类:"))
        self._category_combo = QComboBox()
        self._category_combo.addItems(CATEGORIES)
        self._category_combo.setEditable(True)
        self._category_combo.currentIndexChanged.connect(self._on_field_changed)
        cat_row.addWidget(self._category_combo, 1)
        detail_layout.addLayout(cat_row)

        # USDA status (read-only)
        self._detail_usda = QLabel()
        detail_layout.addWidget(self._detail_usda)

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

        # Reverse lookup: recipes using this ingredient
        self._ref_label = QLabel("引用菜谱:")
        self._ref_label.setStyleSheet("font-weight: bold; margin-top: 6px;")
        detail_layout.addWidget(self._ref_label)
        self._ref_list = QListWidget()
        self._ref_list.setMaximumHeight(120)
        self._ref_list.itemDoubleClicked.connect(self._on_ref_double_clicked)
        detail_layout.addWidget(self._ref_list)

        layout.addWidget(self._detail_frame)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_ingredient_manager(self, mgr: IngredientManager):
        """Set the ingredient manager and refresh the list."""
        self._mgr = mgr
        self.refresh_list()

    def set_file_manager(self, fm: FileManager):
        """Set the file manager for reverse lookup."""
        self._fm = fm

    def refresh_list(self):
        """Reload ingredients from the manager into the tree."""
        self._tree.clear()
        if self._mgr is None:
            return

        # Compute usage counts for color coding
        ingredient_counts: dict[str, int] = {}
        if self._fm:
            ingredient_counts, _ = self._fm.compute_usage_counts()

        query = self._search_edit.text().strip().lower()
        ingredients = self._mgr.search(query) if query else self._mgr.get_all()

        # Group by category using the defined order
        by_category: dict[str, list] = {cat: [] for cat in CATEGORIES}
        for ing in ingredients:
            cat = ing.category if ing.category in by_category else "其他"
            by_category[cat].append(ing)

        for cat in CATEGORIES:
            items = by_category[cat]
            cat_item = QTreeWidgetItem(self._tree, [f"{cat} ({len(items)})"])
            cat_item.setData(0, Qt.ItemDataRole.UserRole, None)
            cat_item.setExpanded(True)
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)

            for ing in sorted(items, key=lambda i: i.name):
                match_icon = "✓" if ing.usda_match_status == "matched" else "○"
                # Count usage across all matching names
                names = {ing.name} | set(ing.aliases)
                usage = sum(ingredient_counts.get(n, 0) for n in names)
                text = f"{ing.name}  {match_icon}  [{usage}]"
                child = QTreeWidgetItem(cat_item, [text])
                child.setData(0, Qt.ItemDataRole.UserRole, ing)
                if usage == 0:
                    child.setForeground(0, QColor("#CC0000"))
                elif usage <= 2:
                    child.setForeground(0, QColor("#CC8800"))

        self._detail_frame.setVisible(False)
        self._selected_ingredient = None

    def get_all_ingredient_names(self) -> list[str]:
        """Return all ingredient names and aliases (for auto-completion)."""
        if self._mgr is None:
            return []
        names: list[str] = []
        for ing in self._mgr.get_all():
            names.append(ing.name)
            names.extend(ing.aliases)
        return names

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_search(self, text: str):
        self.refresh_list()

    def _on_item_changed(self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None):
        if current is None:
            self._detail_frame.setVisible(False)
            self._selected_ingredient = None
            return

        ing = current.data(0, Qt.ItemDataRole.UserRole)
        if ing is None:
            self._detail_frame.setVisible(False)
            self._selected_ingredient = None
            return

        self._selected_ingredient = ing
        self._populate_detail(ing)
        self._detail_frame.setVisible(True)

    def _populate_detail(self, ing):
        """Fill the detail form with ingredient data."""
        self._name_edit.blockSignals(True)
        self._alias_edit.blockSignals(True)
        self._category_combo.blockSignals(True)

        self._detail_title.setText(ing.name)
        self._name_edit.setText(ing.name)
        self._alias_edit.setText(", ".join(ing.aliases))

        idx = self._category_combo.findText(ing.category)
        if idx >= 0:
            self._category_combo.setCurrentIndex(idx)
        else:
            self._category_combo.setEditText(ing.category)

        usda_status = "已匹配" if ing.usda_match_status == "matched" else "未匹配"
        self._detail_usda.setText(f"USDA: {usda_status}")

        self._save_btn.setEnabled(False)

        self._name_edit.blockSignals(False)
        self._alias_edit.blockSignals(False)
        self._category_combo.blockSignals(False)

        # Reverse lookup
        self._populate_ref_list(ing)

    def _on_field_changed(self, *_):
        """Enable save button when any field is modified."""
        self._save_btn.setEnabled(True)

    def _on_save(self):
        """Save edited fields back to the ingredient."""
        if self._mgr is None or self._selected_ingredient is None:
            return

        ing = self._selected_ingredient
        new_name = self._name_edit.text().strip()
        if not new_name:
            QMessageBox.warning(self, "无效输入", "食材名称不能为空。")
            return

        # Check name conflict (different ingredient with same name)
        existing = self._mgr.get_by_name(new_name)
        if existing is not None and existing.key != ing.key:
            QMessageBox.warning(
                self, "名称冲突",
                f"已存在名为「{new_name}」的食材，请使用其他名称或通过合并功能处理。"
            )
            return

        # Update via manager
        self._mgr.update(
            key=ing.key,
            name=new_name,
            aliases=[a.strip() for a in self._alias_edit.text().strip().split(",") if a.strip()],
            category=self._category_combo.currentText().strip(),
        )

        self._save_btn.setEnabled(False)
        self.ingredient_changed.emit()
        self.refresh_list()

    def _on_delete(self):
        """Delete the selected ingredient after confirmation."""
        if self._mgr is None or self._selected_ingredient is None:
            return

        name = self._selected_ingredient.name
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除食材「{name}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._mgr.remove(self._selected_ingredient.key)
        self._selected_ingredient = None
        self._detail_frame.setVisible(False)
        self.ingredient_changed.emit()
        self.refresh_list()

    def _on_merge(self):
        """Open merge dialog for the selected ingredient."""
        if self._mgr is None or self._selected_ingredient is None:
            return

        from src.ui.merge_dialog import MergeDialog
        dlg = MergeDialog(
            self._mgr,
            preselect_a=self._selected_ingredient.name,
            parent=self,
        )
        if dlg.exec():
            keep_name, remove_name = dlg.get_merge_params()
            self._mgr.merge(keep_name, remove_name)
            self._selected_ingredient = None
            self._detail_frame.setVisible(False)
            self.ingredient_changed.emit()
            self.refresh_list()

    # ------------------------------------------------------------------
    # Reverse lookup
    # ------------------------------------------------------------------

    def _populate_ref_list(self, ing):
        """Fill the reference list with recipes using this ingredient."""
        self._ref_list.clear()
        names = {ing.name} | set(ing.aliases)
        recipes = self._find_recipes_using_ingredient(names)
        self._ref_label.setText(f"引用菜谱 ({len(recipes)}):")
        for recipe_name in recipes:
            item = QListWidgetItem(recipe_name)
            item.setData(Qt.ItemDataRole.UserRole, f"{recipe_name}.json")
            self._ref_list.addItem(item)

    def _find_recipes_using_ingredient(self, names: set[str]) -> list[str]:
        """Scan all output JSON files for recipes containing any of the given names."""
        if self._fm is None:
            return []
        recipes: list[str] = []
        for path in self._fm.list_output_recipes():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for ing in data.get("ingredients", []):
                    if ing.get("ingredient_name", "") in names:
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
