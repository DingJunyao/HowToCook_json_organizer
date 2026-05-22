# src/ui/ingredient_panel.py
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.managers.ingredient_manager import IngredientManager

CATEGORIES = ["蔬菜", "肉类", "水产", "禽蛋", "豆制品", "主食/谷物", "调料", "饮品", "干货", "其他"]


class IngredientPanel(QWidget):
    """Right-panel ingredient library reference for RecipeTab."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._mgr: IngredientManager | None = None
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

        # Detail area (shown when an ingredient is selected)
        self._detail_frame = QFrame()
        self._detail_frame.setFrameShape(QFrame.StyledPanel)
        self._detail_frame.setVisible(False)
        detail_layout = QVBoxLayout(self._detail_frame)
        detail_layout.setContentsMargins(6, 6, 6, 6)

        self._detail_title = QLabel()
        self._detail_title.setStyleSheet("font-weight: bold; font-size: 13px;")
        detail_layout.addWidget(self._detail_title)

        self._detail_aliases = QLabel()
        self._detail_aliases.setWordWrap(True)
        detail_layout.addWidget(self._detail_aliases)

        self._detail_category = QLabel()
        detail_layout.addWidget(self._detail_category)

        self._detail_usda = QLabel()
        detail_layout.addWidget(self._detail_usda)

        layout.addWidget(self._detail_frame)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_ingredient_manager(self, mgr: IngredientManager):
        """Set the ingredient manager and refresh the list."""
        self._mgr = mgr
        self.refresh_list()

    def refresh_list(self):
        """Reload ingredients from the manager into the tree."""
        self._tree.clear()
        if self._mgr is None:
            return

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
            cat_item.setData(0, Qt.ItemDataRole.UserRole, None)  # category header
            cat_item.setExpanded(True)
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)

            for ing in sorted(items, key=lambda i: i.name):
                match_icon = "✓" if ing.usda_match_status == "matched" else "○"
                child = QTreeWidgetItem(cat_item, [f"{ing.name}  {match_icon}"])
                child.setData(0, Qt.ItemDataRole.UserRole, ing)

        self._detail_frame.setVisible(False)

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
        """Filter the ingredient list based on search text."""
        self.refresh_list()

    def _on_item_changed(self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None):
        """Show detail when an ingredient item is selected."""
        if current is None:
            self._detail_frame.setVisible(False)
            return

        ing = current.data(0, Qt.ItemDataRole.UserRole)
        if ing is None:
            # Category header clicked — hide detail
            self._detail_frame.setVisible(False)
            return

        self._detail_title.setText(ing.name)
        self._detail_aliases.setText(
            f"别名: {', '.join(ing.aliases)}" if ing.aliases else "别名: （无）"
        )
        self._detail_category.setText(f"分类: {ing.category}")
        usda_status = "已匹配" if ing.usda_match_status == "matched" else "未匹配"
        self._detail_usda.setText(f"USDA: {usda_status}")
        self._detail_frame.setVisible(True)
