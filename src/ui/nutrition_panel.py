# src/ui/nutrition_panel.py
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.managers.ingredient_manager import IngredientManager
from src.managers.nutrition_matcher import NutritionMatcher
from src.models.nutrition import NutritionFact, USDAEntry
from src.ui.ingredient_panel import _DEFAULT_CATEGORY_ORDER


class NutritionPanel(QWidget):
    """Handles both center panel (ingredient details + USDA matching) and right
    panel (nutrition detail table) for NutritionTab."""

    ingredient_updated = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._matcher: NutritionMatcher | None = None
        self._manager: IngredientManager | None = None
        self._current_key: str | None = None
        self._current_search_results: list[USDAEntry] = []
        self._on_usda_import_cb: callable | None = None

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._build_center_panel(), 1)
        outer.addWidget(self._build_right_panel(), 1)

    # -- Center Panel --------------------------------------------------------

    def _build_center_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._build_ingredient_info_group())
        layout.addWidget(self._build_usda_match_group(), 1)
        return w

    def _build_ingredient_info_group(self) -> QGroupBox:
        group = QGroupBox("食材详情")
        form = QVBoxLayout(group)

        # Standard name
        form.addWidget(QLabel("标准名称"))
        self._name_edit = QLineEdit()
        form.addWidget(self._name_edit)

        # Aliases
        form.addWidget(QLabel("别名 (逗号分隔)"))
        self._alias_edit = QLineEdit()
        form.addWidget(self._alias_edit)

        # Category
        form.addWidget(QLabel("分类"))
        self._category_combo = QComboBox()
        self._category_combo.addItems(list(_DEFAULT_CATEGORY_ORDER))
        form.addWidget(self._category_combo)

        # Update button
        self._update_btn = QPushButton("更新食材信息")
        self._update_btn.clicked.connect(self._on_update_ingredient)
        form.addWidget(self._update_btn)

        return group

    def _build_usda_match_group(self) -> QGroupBox:
        group = QGroupBox("USDA 匹配")
        layout = QVBoxLayout(group)

        # Status label
        self._status_label = QLabel("未匹配")
        layout.addWidget(self._status_label)

        # Unmatch button
        self._unmatch_btn = QPushButton("取消匹配")
        self._unmatch_btn.clicked.connect(self._on_unmatch)
        layout.addWidget(self._unmatch_btn)

        # "Download USDA data" button (shown when no data)
        self._download_usda_btn = QPushButton("下载 USDA 数据...")
        self._download_usda_btn.setToolTip(
            "从 USDA FoodData Central 下载营养数据并使用 AI 翻译为中文"
        )
        self._download_usda_btn.clicked.connect(self._on_download_usda)
        self._download_usda_btn.setVisible(False)
        layout.addWidget(self._download_usda_btn)

        # Search bar
        search_row = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("搜索 USDA 数据库...")
        self._search_edit.returnPressed.connect(self._on_search)
        search_row.addWidget(self._search_edit)

        self._search_btn = QPushButton("搜索")
        self._search_btn.clicked.connect(self._on_search)
        search_row.addWidget(self._search_btn)
        layout.addLayout(search_row)

        # Candidate list
        self._candidate_list = QListWidget()
        self._candidate_list.itemClicked.connect(self._on_candidate_clicked)
        self._candidate_list.currentItemChanged.connect(self._on_candidate_changed)
        layout.addWidget(self._candidate_list, 1)

        # Match button
        self._match_btn = QPushButton("确认匹配")
        self._match_btn.clicked.connect(self._on_match)
        layout.addWidget(self._match_btn)

        return group

    # -- Right Panel ---------------------------------------------------------

    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        self._nutrition_table = QTableWidget(0, 3)
        self._nutrition_table.setHorizontalHeaderLabels(["营养素(中文)", "含量(每100g)", "单位"])
        self._nutrition_table.horizontalHeader().stretchLastSection = True
        self._nutrition_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._nutrition_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        layout.addWidget(self._nutrition_table)
        return w

    # -- Public API ----------------------------------------------------------

    def set_nutrition_matcher(self, matcher: NutritionMatcher) -> None:
        self._matcher = matcher
        self._update_data_available_ui()

    def set_ingredient_manager(self, mgr: IngredientManager) -> None:
        self._manager = mgr
        self._update_category_combo()

    def set_on_usda_import(self, callback: callable) -> None:
        """Set callback to trigger USDA data download + import.

        The callback will be called when the user clicks "下载 USDA 数据..."
        After the callback returns, set_nutrition_matcher should be called
        with the new matcher.
        """
        self._on_usda_import_cb = callback

    def _update_data_available_ui(self) -> None:
        """Show/hide download button and search controls based on data presence."""
        has_data = self._matcher is not None and self._matcher.has_data
        self._download_usda_btn.setVisible(not has_data)
        self._search_btn.setEnabled(has_data)
        self._search_edit.setEnabled(has_data)
        self._match_btn.setEnabled(has_data)

    def _update_category_combo(self) -> None:
        """Re-populate the category combo box from default order + data."""
        categories = list(_DEFAULT_CATEGORY_ORDER)
        if self._manager:
            for ing in self._manager.get_all():
                if ing.category and ing.category not in categories:
                    categories.append(ing.category)
        self._category_combo.blockSignals(True)
        current = self._category_combo.currentText()
        self._category_combo.clear()
        self._category_combo.addItems(categories)
        idx = self._category_combo.findText(current)
        if idx >= 0:
            self._category_combo.setCurrentIndex(idx)
        elif current:
            self._category_combo.setEditText(current)
        self._category_combo.blockSignals(False)

    def set_ingredient(self, ingredient_key: str) -> None:
        """Load an ingredient's details and match status into the center panel."""
        if self._manager is None:
            return

        self._current_key = ingredient_key
        ing = self._get_ingredient(ingredient_key)
        if ing is None:
            return

        # Populate ingredient info
        self._name_edit.setText(ing.name)
        self._alias_edit.setText(", ".join(ing.aliases))

        idx = self._category_combo.findText(ing.category)
        if idx >= 0:
            self._category_combo.setCurrentIndex(idx)
        else:
            self._category_combo.setCurrentIndex(self._category_combo.count() - 1)

        # Update match status
        self._update_match_status(ing)

        # Auto-fill search with ingredient name and trigger search
        self._search_edit.setText(ing.name)
        self._candidate_list.clear()
        self._current_search_results = []
        if self._matcher and self._matcher.has_data:
            self._on_search()

        # If matched, show nutrition in right panel
        if ing.usda_match_status == "matched" and ing.usda_id is not None and self._matcher:
            nutrients = self._matcher.get_nutrition(ing.usda_id)
            self.show_nutrition(nutrients)
        else:
            self._nutrition_table.setRowCount(0)

    def show_nutrition(self, nutrients: list[NutritionFact]) -> None:
        """Display nutrition facts in the right panel table."""
        self._nutrition_table.setRowCount(len(nutrients))
        for row, fact in enumerate(nutrients):
            self._nutrition_table.setItem(row, 0, QTableWidgetItem(fact.name_zh))
            self._nutrition_table.setItem(row, 1, QTableWidgetItem(str(fact.amount)))
            self._nutrition_table.setItem(row, 2, QTableWidgetItem(fact.unit))
        self._nutrition_table.resizeColumnsToContents()

    # -- Private helpers -----------------------------------------------------

    def _get_ingredient(self, key: str):
        """Retrieve ingredient from manager by key."""
        if self._manager is None:
            return None
        for ing in self._manager.get_all():
            if ing.key == key:
                return ing
        return None

    def _update_match_status(self, ing) -> None:
        """Update the status label and unmatch button visibility."""
        if ing.usda_match_status == "matched" and ing.usda_id is not None:
            if self._matcher:
                entry = self._matcher.get_entry(ing.usda_id)
                desc = entry.description if entry else str(ing.usda_id)
                desc_zh = entry.description_zh if entry else ""
                if desc_zh:
                    text = f"已匹配: {desc_zh} ({desc})"
                else:
                    text = f"已匹配: {desc}"
            else:
                text = f"已匹配: FDC {ing.usda_id}"
            self._status_label.setText(text)
            self._unmatch_btn.setVisible(True)
        else:
            self._status_label.setText("未匹配")
            self._unmatch_btn.setVisible(False)

    # -- Slots ---------------------------------------------------------------

    def _on_update_ingredient(self) -> None:
        """Save updated ingredient info back to the manager."""
        if self._manager is None or self._current_key is None:
            return

        ing = self._get_ingredient(self._current_key)
        if ing is None:
            return

        new_name = self._name_edit.text().strip()
        if not new_name:
            return

        ing.name = new_name
        alias_text = self._alias_edit.text().strip()
        ing.aliases = [a.strip() for a in alias_text.split(",") if a.strip()] if alias_text else []
        ing.category = self._category_combo.currentText()

        self._manager._rebuild_index()
        self.ingredient_updated.emit()

    def _on_search(self) -> None:
        """Search the USDA database and populate candidate list."""
        if self._matcher is None:
            return

        if not self._matcher.has_data:
            self._candidate_list.clear()
            item = QListWidgetItem("⚠ 未加载 USDA 数据，请点击上方「下载 USDA 数据...」按钮")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self._candidate_list.addItem(item)
            return

        query = self._search_edit.text().strip()
        if not query:
            return

        self._current_search_results = self._matcher.search(query)
        self._candidate_list.clear()

        if not self._current_search_results:
            item = QListWidgetItem("（无匹配结果）")
            item.setData(0x0100, None)
            self._candidate_list.addItem(item)
            return

        for entry in self._current_search_results:
            label = f"{entry.description_zh} ({entry.description})" if entry.description_zh else entry.description
            item = QListWidgetItem(label)
            item.setData(0x0100, entry.fdc_id)
            self._candidate_list.addItem(item)

    def _on_candidate_clicked(self, item: QListWidgetItem) -> None:
        """Show nutrition preview when a candidate is clicked."""
        fdc_id = item.data(0x0100)
        if not isinstance(fdc_id, int) or self._matcher is None:
            return
        nutrients = self._matcher.get_nutrition(fdc_id)
        if nutrients:
            self.show_nutrition(nutrients)

    def _on_candidate_changed(self, current: QListWidgetItem, _previous: QListWidgetItem) -> None:
        """Show nutrition preview when the current candidate changes (click or keyboard)."""
        if current is not None:
            self._on_candidate_clicked(current)

    def _on_match(self) -> None:
        """Confirm match between selected ingredient and selected USDA entry."""
        if self._manager is None or self._current_key is None:
            return

        current_item = self._candidate_list.currentItem()
        if current_item is None:
            return

        fdc_id = current_item.data(0x0100)
        if not isinstance(fdc_id, int):
            return

        ing = self._get_ingredient(self._current_key)
        if ing is None:
            return

        ing.usda_id = fdc_id
        ing.usda_match_status = "matched"

        self._update_match_status(ing)
        self.ingredient_updated.emit()

    def _on_unmatch(self) -> None:
        """Remove USDA match from the current ingredient."""
        if self._manager is None or self._current_key is None:
            return

        ing = self._get_ingredient(self._current_key)
        if ing is None:
            return

        ing.usda_id = None
        ing.usda_match_status = "unmatched"

        self._update_match_status(ing)
        self._nutrition_table.setRowCount(0)
        self.ingredient_updated.emit()

    def _on_download_usda(self) -> None:
        """Trigger USDA data download via callback set by main window."""
        if self._on_usda_import_cb:
            self._on_usda_import_cb()
