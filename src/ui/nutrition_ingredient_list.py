from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.managers.ingredient_manager import IngredientManager
from src.ui.ingredient_panel import _DEFAULT_CATEGORY_ORDER


class NutritionIngredientList(QWidget):
    ingredient_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._manager: IngredientManager | None = None
        self._filter_mode: str = "全部"
        self._search_text: str = ""
        self._categories: list[str] = list(_DEFAULT_CATEGORY_ORDER)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Filter buttons
        filter_row = QHBoxLayout()
        self._btn_all = QPushButton("全部")
        self._btn_matched = QPushButton("已匹配")
        self._btn_unmatched = QPushButton("未匹配")
        for btn in (self._btn_all, self._btn_matched, self._btn_unmatched):
            btn.setCheckable(True)
            filter_row.addWidget(btn)
        self._btn_all.setChecked(True)
        self._btn_all.clicked.connect(lambda: self._set_filter("全部"))
        self._btn_matched.clicked.connect(lambda: self._set_filter("已匹配"))
        self._btn_unmatched.clicked.connect(lambda: self._set_filter("未匹配"))
        layout.addLayout(filter_row)

        # Search bar
        self._search_bar = QLineEdit()
        self._search_bar.setPlaceholderText("搜索食材...")
        self._search_bar.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search_bar)

        # Ingredient tree (multi-select via Ctrl+Click)
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setSelectionMode(
            QTreeWidget.SelectionMode.ExtendedSelection
        )
        self._tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._tree)

    # -- public API ----------------------------------------------------------

    def set_ingredient_manager(self, mgr: IngredientManager) -> None:
        self._manager = mgr
        self._rebuild_categories()
        self.refresh_list()

    def _rebuild_categories(self) -> None:
        """Build ordered category list from default order + data."""
        categories = list(_DEFAULT_CATEGORY_ORDER)
        if self._manager:
            for ing in self._manager.get_all():
                if ing.category and ing.category not in categories:
                    categories.append(ing.category)
        self._categories = categories

    def refresh_list(self) -> None:
        self._tree.clear()
        if self._manager is None:
            return

        ingredients = self._manager.get_all()

        for cat in self._categories:
            cat_items: list[QTreeWidgetItem] = []
            for ing in ingredients:
                if ing.category != cat:
                    continue
                if not self._passes_filter(ing):
                    continue
                if not self._passes_search(ing):
                    continue

                status_text = "✓ 已匹配" if ing.usda_match_status == "matched" else "○ 未匹配"
                item = QTreeWidgetItem([f"{ing.name}  {status_text}"])
                item.setData(0, 0x0100, ing.key)
                cat_items.append(item)

            if not cat_items:
                continue

            cat_item = QTreeWidgetItem([cat])
            for child in cat_items:
                cat_item.addChild(child)
            self._tree.addTopLevelItem(cat_item)
            cat_item.setExpanded(True)

    def get_selected_key(self) -> str | None:
        item = self._tree.currentItem()
        if item is None:
            return None
        key = item.data(0, 0x0100)
        return key if isinstance(key, str) else None

    def get_selected_keys(self) -> list[str]:
        """Return keys of all selected ingredient items (excludes category items)."""
        keys: list[str] = []
        for item in self._tree.selectedItems():
            key = item.data(0, 0x0100)
            if isinstance(key, str):
                keys.append(key)
        return keys

    # -- private helpers -----------------------------------------------------

    def _passes_filter(self, ing) -> bool:
        if self._filter_mode == "全部":
            return True
        if self._filter_mode == "已匹配":
            return ing.usda_match_status == "matched"
        if self._filter_mode == "未匹配":
            return ing.usda_match_status != "matched"
        return True

    def _passes_search(self, ing) -> bool:
        if not self._search_text:
            return True
        keywords = self._search_text.lower().split()
        name = ing.name.lower()
        aliases = [a.lower() for a in ing.aliases]
        return all(kw in name or any(kw in a for a in aliases) for kw in keywords)

    def _set_filter(self, mode: str) -> None:
        self._filter_mode = mode
        btn_map = {"全部": self._btn_all, "已匹配": self._btn_matched, "未匹配": self._btn_unmatched}
        for name, btn in btn_map.items():
            btn.setChecked(name == mode)
        self.refresh_list()

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text.strip()
        self.refresh_list()

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        key = item.data(0, 0x0100)
        if isinstance(key, str):
            self.ingredient_selected.emit(key)
