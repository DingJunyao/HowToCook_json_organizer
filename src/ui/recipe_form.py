# src/ui/recipe_form.py
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QScrollArea,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHeaderView,
    QGroupBox,
    QHBoxLayout,
    QSizePolicy,
    QCompleter,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DIFFICULTY_OPTIONS = ["", "★", "★★", "★★★", "★★★★", "★★★★★"]
DIFFICULTY_STAR_TO_WORD = {"": "", "★": "simple", "★★": "easy", "★★★": "medium", "★★★★": "hard", "★★★★★": "expert"}
DIFFICULTY_WORD_TO_STAR = {v: k for k, v in DIFFICULTY_STAR_TO_WORD.items()}
CATEGORY_OPTIONS = [
    "",
    "荤菜",
    "素菜",
    "水产",
    "早餐",
    "主食",
    "汤与粥",
    "调料",
    "甜品",
    "饮料",
    "半成品",
]

INGREDIENT_COLUMNS = ["食材名称", "关联", "数量", "单位", "范围(最小)", "范围(最大)", "用量描述", "是否可选", "备注"]

QTY_DESC_OPTIONS = ["", "适量", "少许"]
STEP_COLUMNS = ["序号", "描述", "用时(分钟)", "备注"]
TIP_COLUMNS = ["序号", "内容"]


# ---------------------------------------------------------------------------
# RecipeForm
# ---------------------------------------------------------------------------


class RecipeForm(QWidget):
    """Scrollable form for editing a single recipe."""

    save_requested = Signal(dict)  # emitted when user clicks Save

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dirty = False
        self._im = None  # IngredientManager reference
        self._um = None  # UnitManager reference
        self._build_ui()
        self._connect_change_signals()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(6, 6, 6, 6)
        self._layout.setSpacing(8)

        self._add_basic_info_section()
        self._add_ingredients_section()
        self._add_steps_section()
        self._add_tips_section()
        self._add_bottom_buttons()

        self._layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)

    # --- Basic info -------------------------------------------------------

    def _add_basic_info_section(self):
        group = QGroupBox("基本信息")
        form = QFormLayout(group)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("菜谱名称")
        form.addRow("名称:", self.name_edit)

        self.difficulty_combo = QComboBox()
        self.difficulty_combo.addItems(DIFFICULTY_OPTIONS)
        self.difficulty_combo.setEditable(True)
        form.addRow("难度:", self.difficulty_combo)

        self.category_combo = QComboBox()
        self.category_combo.addItems(CATEGORY_OPTIONS)
        self.category_combo.setEditable(True)
        form.addRow("分类:", self.category_combo)

        self.servings_spin = QSpinBox()
        self.servings_spin.setRange(1, 9999)
        self.servings_spin.setValue(1)
        form.addRow("份量:", self.servings_spin)

        self.original_servings_spin = QSpinBox()
        self.original_servings_spin.setRange(1, 9999)
        self.original_servings_spin.setValue(1)
        form.addRow("原始份量:", self.original_servings_spin)

        self._layout.addWidget(group)

    # --- Ingredients ------------------------------------------------------

    def _add_ingredients_section(self):
        group = QGroupBox("食材")
        vbox = QVBoxLayout(group)

        # Buttons row
        btn_row = QHBoxLayout()
        self.add_ingredient_btn = QPushButton("添加食材")
        self.remove_ingredient_btn = QPushButton("删除选中")
        self.ingredient_up_btn = QPushButton("▲")
        self.ingredient_up_btn.setFixedWidth(30)
        self.ingredient_up_btn.setToolTip("上移")
        self.ingredient_down_btn = QPushButton("▼")
        self.ingredient_down_btn.setFixedWidth(30)
        self.ingredient_down_btn.setToolTip("下移")
        btn_row.addWidget(self.add_ingredient_btn)
        btn_row.addWidget(self.remove_ingredient_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.ingredient_up_btn)
        btn_row.addWidget(self.ingredient_down_btn)
        vbox.addLayout(btn_row)

        # Table
        self.ingredients_table = QTableWidget(0, len(INGREDIENT_COLUMNS))
        self.ingredients_table.setHorizontalHeaderLabels(INGREDIENT_COLUMNS)
        header = self.ingredients_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.ingredients_table.setColumnWidth(1, 50)
        self.ingredients_table.setColumnWidth(6, 70)
        self.ingredients_table.setColumnWidth(7, 50)
        self.ingredients_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectItems
        )
        self.ingredients_table.setSelectionMode(
            QTableWidget.SelectionMode.ExtendedSelection
        )
        self.ingredients_table.setEditTriggers(
            QTableWidget.EditTrigger.CurrentChanged
            | QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.EditKeyPressed
        )
        self.ingredients_table.setMinimumHeight(120)
        self.ingredients_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        vbox.addWidget(self.ingredients_table)

        # Connect buttons
        self.add_ingredient_btn.clicked.connect(self._add_ingredient_row)
        self.remove_ingredient_btn.clicked.connect(self._remove_ingredient_row)
        self.ingredient_up_btn.clicked.connect(lambda: self._move_row(self.ingredients_table, -1))
        self.ingredient_down_btn.clicked.connect(lambda: self._move_row(self.ingredients_table, 1))

        self._layout.addWidget(group)

    def _add_ingredient_row(self):
        row = self.ingredients_table.rowCount()
        self.ingredients_table.insertRow(row)
        # Unit combo box
        self.ingredients_table.setCellWidget(row, 3, self._create_unit_combo())
        # "用量描述" combo (col 6)
        self.ingredients_table.setCellWidget(row, 6, self._create_qty_desc_combo())
        # "是否可选" checkbox (col 7)
        opt_item = QTableWidgetItem()
        opt_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        opt_item.setCheckState(Qt.CheckState.Unchecked)
        self.ingredients_table.setItem(row, 7, opt_item)
        self._update_link_status(row)

    def _remove_ingredient_row(self):
        rows = sorted(
            set(idx.row() for idx in self.ingredients_table.selectedIndexes()),
            reverse=True,
        )
        for r in rows:
            self.ingredients_table.removeRow(r)

    # --- Steps ------------------------------------------------------------

    def _add_steps_section(self):
        group = QGroupBox("步骤")
        vbox = QVBoxLayout(group)

        # Buttons row
        btn_row = QHBoxLayout()
        self.add_step_btn = QPushButton("添加步骤")
        self.remove_step_btn = QPushButton("删除选中")
        self.step_up_btn = QPushButton("▲")
        self.step_up_btn.setFixedWidth(30)
        self.step_up_btn.setToolTip("上移")
        self.step_down_btn = QPushButton("▼")
        self.step_down_btn.setFixedWidth(30)
        self.step_down_btn.setToolTip("下移")
        btn_row.addWidget(self.add_step_btn)
        btn_row.addWidget(self.remove_step_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.step_up_btn)
        btn_row.addWidget(self.step_down_btn)
        vbox.addLayout(btn_row)

        # Table
        self.steps_table = QTableWidget(0, len(STEP_COLUMNS))
        self.steps_table.setHorizontalHeaderLabels(STEP_COLUMNS)
        header = self.steps_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.steps_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectItems
        )
        self.steps_table.setSelectionMode(
            QTableWidget.SelectionMode.ExtendedSelection
        )
        self.steps_table.setEditTriggers(
            QTableWidget.EditTrigger.CurrentChanged
            | QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.EditKeyPressed
        )
        self.steps_table.setMinimumHeight(120)
        self.steps_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        vbox.addWidget(self.steps_table)

        # Connect buttons
        self.add_step_btn.clicked.connect(self._add_step_row)
        self.remove_step_btn.clicked.connect(self._remove_step_row)
        self.step_up_btn.clicked.connect(lambda: self._move_row(self.steps_table, -1))
        self.step_down_btn.clicked.connect(lambda: self._move_row(self.steps_table, 1))

        self._layout.addWidget(group)

    def _add_step_row(self):
        row = self.steps_table.rowCount()
        self.steps_table.insertRow(row)
        self._renumber_steps()

    def _remove_step_row(self):
        rows = sorted(
            set(idx.row() for idx in self.steps_table.selectedIndexes()),
            reverse=True,
        )
        for r in rows:
            self.steps_table.removeRow(r)
        self._renumber_steps()

    def _renumber_steps(self):
        for row in range(self.steps_table.rowCount()):
            item = self.steps_table.item(row, 0)
            if item is None:
                item = QTableWidgetItem()
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # non-editable
                self.steps_table.setItem(row, 0, item)
            item.setText(str(row + 1))

    # --- Tips -------------------------------------------------------------

    def _add_tips_section(self):
        group = QGroupBox("小贴士")
        vbox = QVBoxLayout(group)

        # Buttons row
        btn_row = QHBoxLayout()
        self.add_tip_btn = QPushButton("添加")
        self.remove_tip_btn = QPushButton("删除选中")
        self.tip_up_btn = QPushButton("▲")
        self.tip_up_btn.setFixedWidth(30)
        self.tip_up_btn.setToolTip("上移")
        self.tip_down_btn = QPushButton("▼")
        self.tip_down_btn.setFixedWidth(30)
        self.tip_down_btn.setToolTip("下移")
        btn_row.addWidget(self.add_tip_btn)
        btn_row.addWidget(self.remove_tip_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.tip_up_btn)
        btn_row.addWidget(self.tip_down_btn)
        vbox.addLayout(btn_row)

        # Table
        self.tips_table = QTableWidget(0, len(TIP_COLUMNS))
        self.tips_table.setHorizontalHeaderLabels(TIP_COLUMNS)
        header = self.tips_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tips_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.tips_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.tips_table.setEditTriggers(
            QTableWidget.EditTrigger.CurrentChanged
            | QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.EditKeyPressed
        )
        self.tips_table.setMinimumHeight(80)
        self.tips_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        vbox.addWidget(self.tips_table)

        # Connect buttons
        self.add_tip_btn.clicked.connect(self._add_tip_row)
        self.remove_tip_btn.clicked.connect(self._remove_tip_row)
        self.tip_up_btn.clicked.connect(lambda: self._move_row(self.tips_table, -1))
        self.tip_down_btn.clicked.connect(lambda: self._move_row(self.tips_table, 1))

        self._layout.addWidget(group)

    def _add_tip_row(self):
        row = self.tips_table.rowCount()
        self.tips_table.insertRow(row)
        self._renumber_tips()

    def _remove_tip_row(self):
        rows = sorted(
            set(idx.row() for idx in self.tips_table.selectedIndexes()),
            reverse=True,
        )
        for r in rows:
            self.tips_table.removeRow(r)
        self._renumber_tips()

    def _renumber_tips(self):
        for row in range(self.tips_table.rowCount()):
            item = self.tips_table.item(row, 0)
            if item is None:
                item = QTableWidgetItem()
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.tips_table.setItem(row, 0, item)
            item.setText(str(row + 1))

    # --- Bottom buttons ---------------------------------------------------

    def _add_bottom_buttons(self):
        row = QHBoxLayout()
        self.save_btn = QPushButton("保存")
        self.clear_btn = QPushButton("清空")
        row.addWidget(self.save_btn)
        row.addWidget(self.clear_btn)
        row.addStretch()

        self.save_btn.clicked.connect(self._on_save_clicked)
        self.clear_btn.clicked.connect(self.clear_form)

        self._layout.addLayout(row)

    # ------------------------------------------------------------------
    # Dirty tracking & signal wiring
    # ------------------------------------------------------------------

    def _connect_change_signals(self):
        """Connect all editable widgets to mark the form as dirty."""
        self.name_edit.textChanged.connect(self._mark_dirty)
        self.difficulty_combo.editTextChanged.connect(self._mark_dirty)
        self.difficulty_combo.currentIndexChanged.connect(self._mark_dirty)
        self.category_combo.editTextChanged.connect(self._mark_dirty)
        self.category_combo.currentIndexChanged.connect(self._mark_dirty)
        self.servings_spin.valueChanged.connect(self._mark_dirty)
        self.original_servings_spin.valueChanged.connect(self._mark_dirty)
        self.ingredients_table.cellChanged.connect(self._on_ingredient_cell_changed)
        self.steps_table.cellChanged.connect(self._on_step_cell_changed)
        self.tips_table.cellChanged.connect(self._on_tip_cell_changed)

        # Clean invisible chars on focus-out for line edits
        self.name_edit.editingFinished.connect(
            lambda: self._clean_line_edit(self.name_edit)
        )
        self.difficulty_combo.lineEdit().editingFinished.connect(
            lambda: self._clean_line_edit(self.difficulty_combo.lineEdit())
        )
        self.category_combo.lineEdit().editingFinished.connect(
            lambda: self._clean_line_edit(self.category_combo.lineEdit())
        )

    @staticmethod
    def _strip_invisible(text: str) -> str:
        """Remove invisible characters and whitespace from both ends."""
        return text.strip("﻿​‌‍⁠      　 ").strip()

    def _clean_cell(self, table: QTableWidget, row: int, col: int):
        """Clean invisible chars from a table cell."""
        item = table.item(row, col)
        if item is None:
            return
        cleaned = self._strip_invisible(item.text())
        if cleaned != item.text():
            table.blockSignals(True)
            item.setText(cleaned)
            table.blockSignals(False)

    def _clean_line_edit(self, edit: QLineEdit):
        """Clean invisible chars from a QLineEdit."""
        cleaned = self._strip_invisible(edit.text())
        if cleaned != edit.text():
            edit.blockSignals(True)
            edit.setText(cleaned)
            edit.blockSignals(False)

    def _on_ingredient_cell_changed(self, row: int, col: int):
        self._dirty = True
        # Skip non-text columns: 1 (link, non-editable), 6 (用量描述 combo), 7 (可选 checkbox)
        if col not in (1, 6, 7):
            self._clean_cell(self.ingredients_table, row, col)
        if col == 0:
            self._update_link_status(row)

    def _on_step_cell_changed(self, row: int, col: int):
        self._dirty = True
        # Skip col 0 (non-editable number)
        if col != 0:
            self._clean_cell(self.steps_table, row, col)

    def _on_tip_cell_changed(self, row: int, col: int):
        self._dirty = True
        # Skip col 0 (non-editable number)
        if col != 0:
            self._clean_cell(self.tips_table, row, col)

    def _mark_dirty(self, *_):
        self._dirty = True

    def _move_row(self, table: QTableWidget, direction: int):
        """Move the current row up (direction=-1) or down (direction=+1)."""
        row = table.currentRow()
        if row < 0:
            return
        target = row + direction
        if target < 0 or target >= table.rowCount():
            return
        # Swap all cell contents
        for col in range(table.columnCount()):
            src_item = table.takeItem(row, col)
            dst_item = table.takeItem(target, col)
            table.setItem(row, col, dst_item)
            table.setItem(target, col, src_item)
        table.selectRow(target)
        # Steps need renumbering after reorder
        if table is self.steps_table:
            self._renumber_steps()
        self._dirty = True

    def is_dirty(self) -> bool:
        """Return whether the form has unsaved changes."""
        return self._dirty

    def set_clean(self):
        """Mark the form as having no unsaved changes."""
        self._dirty = False

    def _on_save_clicked(self):
        """Collect form data and emit save_requested."""
        data = self.collect_data()
        self.save_requested.emit(data)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_recipe(self, data: dict) -> None:
        """Populate the form from parsed Markdown or existing JSON data."""
        self.clear_form()
        self._dirty = False  # clear_form triggers change signals; reset after

        # Basic info
        self.name_edit.setText(data.get("name", ""))

        difficulty = data.get("difficulty", "")
        # Map English word to star display
        star = DIFFICULTY_WORD_TO_STAR.get(difficulty, difficulty)
        idx = self.difficulty_combo.findText(star)
        if idx >= 0:
            self.difficulty_combo.setCurrentIndex(idx)
        else:
            self.difficulty_combo.setEditText(star)

        category = data.get("category", "")
        idx = self.category_combo.findText(category)
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        else:
            self.category_combo.setEditText(category)

        self.servings_spin.setValue(data.get("servings", 1))
        self.original_servings_spin.setValue(data.get("original_servings", 1))

        # Ingredients
        for ing in data.get("ingredients", []):
            self._add_ingredient_row_from(ing)

        # Steps
        for step in data.get("steps", []):
            self._add_step_row_from(step)
        self._renumber_steps()

        # Tips
        tips = data.get("tips", [])
        for tip in tips:
            self._add_tip_row_from(tip)
        self._renumber_tips()

        self._dirty = False  # reset after all fields are populated

    def collect_data(self) -> dict:
        """Gather all form fields into a dict matching the Recipe JSON structure."""
        ingredients = []
        for row in range(self.ingredients_table.rowCount()):
            ing = self._collect_ingredient_row(row)
            ingredients.append(ing)

        steps = []
        for row in range(self.steps_table.rowCount()):
            step = self._collect_step_row(row)
            steps.append(step)

        tips = []
        for row in range(self.tips_table.rowCount()):
            item = self.tips_table.item(row, 1)
            text = item.text().strip() if item else ""
            if text:
                tips.append(text)

        return {
            "name": self.name_edit.text().strip(),
            "source_file": "",
            "category": self.category_combo.currentText().strip(),
            "difficulty": DIFFICULTY_STAR_TO_WORD.get(
                self.difficulty_combo.currentText().strip(),
                self.difficulty_combo.currentText().strip(),
            ),
            "total_time_minutes": None,
            "servings": self.servings_spin.value(),
            "original_servings": self.original_servings_spin.value(),
            "images": [],
            "ingredients": ingredients,
            "steps": steps,
            "tips": tips,
        }

    def clear_form(self) -> None:
        """Reset all fields to defaults."""
        self.name_edit.clear()
        self.difficulty_combo.setCurrentIndex(0)
        self.category_combo.setCurrentIndex(0)
        self.servings_spin.setValue(1)
        self.original_servings_spin.setValue(1)
        self.ingredients_table.setRowCount(0)
        self.steps_table.setRowCount(0)
        self.tips_table.setRowCount(0)
        self._dirty = False

    def set_ingredient_manager(self, mgr):
        """Set the ingredient manager for auto-completion and linking."""
        self._im = mgr
        self._update_completer()

    def set_unit_manager(self, mgr):
        """Set the unit manager for unit dropdown population."""
        self._um = mgr
        self._refresh_unit_combos()

    def _create_unit_combo(self, selected: str = "") -> QComboBox:
        """Create a QComboBox for the unit column."""
        combo = QComboBox()
        combo.setEditable(True)
        if self._um:
            combo.addItems(self._um.get_display_names())
        if selected:
            idx = combo.findText(selected)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setEditText(selected)
        combo.currentIndexChanged.connect(self._mark_dirty)
        combo.editTextChanged.connect(self._mark_dirty)
        return combo

    def _create_qty_desc_combo(self, selected: str = "") -> QComboBox:
        """Create a QComboBox for the '用量描述' column (精确/适量/少许)."""
        combo = QComboBox()
        combo.addItems(QTY_DESC_OPTIONS)
        if selected:
            idx = combo.findText(selected)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setCurrentIndex(0)
        # When selection changes, update quantity cell states
        combo.currentIndexChanged.connect(lambda: self._on_qty_desc_changed(combo))
        return combo

    def _on_qty_desc_changed(self, combo: QComboBox):
        self._mark_dirty()
        # Find the row for this combo
        for row in range(self.ingredients_table.rowCount()):
            if self.ingredients_table.cellWidget(row, 6) is combo:
                self._update_approx_state(row)
                return

    def _refresh_unit_combos(self):
        """Refresh all unit combo boxes in the ingredient table."""
        for row in range(self.ingredients_table.rowCount()):
            combo = self.ingredients_table.cellWidget(row, 3)
            if isinstance(combo, QComboBox):
                current = combo.currentText()
                combo.blockSignals(True)
                combo.clear()
                if self._um:
                    combo.addItems(self._um.get_display_names())
                idx = combo.findText(current)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                else:
                    combo.setEditText(current)
                combo.blockSignals(False)

    def batch_rename_unit(self, old_name: str, new_name: str):
        """Replace unit text across all ingredient rows."""
        for row in range(self.ingredients_table.rowCount()):
            combo = self.ingredients_table.cellWidget(row, 3)
            if isinstance(combo, QComboBox) and combo.currentText() == old_name:
                idx = combo.findText(new_name)
                combo.blockSignals(True)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                else:
                    combo.setEditText(new_name)
                combo.blockSignals(False)
        self._dirty = True

    def _update_completer(self):
        """Update the auto-completer with ingredient names and aliases."""
        if self._im is None:
            return
        names = []
        for ing in self._im.get_all():
            names.append(ing.name)
            names.extend(ing.aliases)
        self._completer = QCompleter(sorted(set(names)))
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)

    def _update_approx_state(self, row: int):
        """When '用量描述' is set, clear and gray out quantity/range cells."""
        combo = self.ingredients_table.cellWidget(row, 6)
        is_approx = isinstance(combo, QComboBox) and combo.currentText() != ""
        gray = Qt.GlobalColor.gray
        black = Qt.GlobalColor.black
        for col in (2, 4, 5):
            item = self.ingredients_table.item(row, col)
            if item is None:
                continue
            if is_approx:
                self.ingredients_table.blockSignals(True)
                item.setText("")
                item.setForeground(gray)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.ingredients_table.blockSignals(False)
            else:
                item.setForeground(black)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)

    def _update_link_status(self, row: int):
        """Update the link status icon for an ingredient row."""
        name_item = self.ingredients_table.item(row, 0)
        link_item = self.ingredients_table.item(row, 1)
        if name_item is None:
            return
        name = name_item.text().strip()
        if link_item is None:
            link_item = QTableWidgetItem()
            link_item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # non-editable
            self.ingredients_table.setItem(row, 1, link_item)
        if not name:
            link_item.setText("—")
            link_item.setForeground(Qt.GlobalColor.gray)
            return
        if self._im and self._im.get_by_name(name):
            link_item.setText("✓")
            link_item.setForeground(Qt.GlobalColor.darkGreen)
            link_item.setToolTip(f"已关联: {self._im.get_by_name(name).name}")
        else:
            link_item.setText("○ 新")
            link_item.setForeground(Qt.GlobalColor.darkYellow)
            link_item.setToolTip("未关联，保存时将自动添加到食材库")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_ingredient_row_from(self, ing: dict) -> None:
        row = self.ingredients_table.rowCount()
        self.ingredients_table.insertRow(row)

        # 食材名称
        self.ingredients_table.setItem(
            row, 0, QTableWidgetItem(ing.get("ingredient_name", ""))
        )

        # 关联状态 (col 1)
        self._update_link_status(row)

        # 数量
        quantity = ing.get("quantity")
        qty_text = str(quantity) if quantity is not None else ""
        self.ingredients_table.setItem(row, 2, QTableWidgetItem(qty_text))

        # 单位 (combo box)
        self.ingredients_table.setCellWidget(
            row, 3, self._create_unit_combo(ing.get("unit", ""))
        )

        # 范围(最小)
        qty_range = ing.get("quantity_range")
        range_min = str(qty_range["min"]) if qty_range and "min" in qty_range else ""
        self.ingredients_table.setItem(row, 4, QTableWidgetItem(range_min))

        # 范围(最大)
        range_max = str(qty_range["max"]) if qty_range and "max" in qty_range else ""
        self.ingredients_table.setItem(row, 5, QTableWidgetItem(range_max))

        # "用量描述" combo (col 6)
        qty_desc = ""
        if ing.get("is_approximate"):
            qty_desc = qty_text if qty_text in ("适量", "少许") else "适量"
        elif qty_text in ("适量", "少许"):
            qty_desc = qty_text
        self.ingredients_table.setCellWidget(
            row, 6, self._create_qty_desc_combo(qty_desc)
        )

        # 是否可选 (col 7)
        opt_item = QTableWidgetItem()
        opt_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        opt_item.setCheckState(
            Qt.CheckState.Checked if ing.get("is_optional", False)
            else Qt.CheckState.Unchecked
        )
        self.ingredients_table.setItem(row, 7, opt_item)

        # 备注 (col 8)
        self.ingredients_table.setItem(
            row, 8, QTableWidgetItem(ing.get("note", ""))
        )

    def _add_step_row_from(self, step: dict) -> None:
        row = self.steps_table.rowCount()
        self.steps_table.insertRow(row)

        # 序号 (auto-generated, non-editable)
        num_item = QTableWidgetItem(str(step.get("step", row + 1)))
        num_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.steps_table.setItem(row, 0, num_item)

        # 描述
        self.steps_table.setItem(
            row, 1, QTableWidgetItem(step.get("content", ""))
        )

        # 用时(分钟)
        duration = step.get("duration_minutes")
        dur_text = str(duration) if duration is not None else ""
        self.steps_table.setItem(row, 2, QTableWidgetItem(dur_text))

        # 备注
        self.steps_table.setItem(
            row, 3, QTableWidgetItem(step.get("tips", ""))
        )

    def _add_tip_row_from(self, tip) -> None:
        row = self.tips_table.rowCount()
        self.tips_table.insertRow(row)
        text = tip if isinstance(tip, str) else str(tip)
        self.tips_table.setItem(row, 1, QTableWidgetItem(text))

    def _collect_ingredient_row(self, row: int) -> dict:
        def _text(col: int) -> str:
            item = self.ingredients_table.item(row, col)
            return item.text().strip() if item else ""

        name = _text(0)
        qty_str = _text(2)
        # Unit from combo box
        unit_combo = self.ingredients_table.cellWidget(row, 3)
        unit = unit_combo.currentText().strip() if isinstance(unit_combo, QComboBox) else _text(3)
        range_min_str = _text(4)
        range_max_str = _text(5)
        # "用量描述" combo (col 6)
        qty_desc_combo = self.ingredients_table.cellWidget(row, 6)
        qty_desc = qty_desc_combo.currentText().strip() if isinstance(qty_desc_combo, QComboBox) else ""
        is_approximate = qty_desc != ""
        # "是否可选" checkbox (col 7)
        opt_item = self.ingredients_table.item(row, 7)
        is_optional = (
            opt_item.checkState() == Qt.CheckState.Checked if opt_item else False
        )
        note = _text(8)

        # Parse quantity
        quantity = None
        if qty_str:
            try:
                quantity = float(qty_str)
            except ValueError:
                quantity = None

        # Parse range
        quantity_range = None
        if range_min_str or range_max_str:
            try:
                rmin = float(range_min_str) if range_min_str else None
                rmax = float(range_max_str) if range_max_str else None
                if rmin is not None or rmax is not None:
                    quantity_range = {}
                    if rmin is not None:
                        quantity_range["min"] = rmin
                    if rmax is not None:
                        quantity_range["max"] = rmax
            except ValueError:
                quantity_range = None

        return {
            "ingredient_name": name,
            "quantity": None if is_approximate else quantity,
            "unit": unit,
            "quantity_range": None if is_approximate else quantity_range,
            "is_approximate": is_approximate,
            "quantity_description": qty_desc,
            "is_optional": is_optional,
            "note": note,
            "original_quantity": "",
            "is_estimated": False,
        }

    def _collect_step_row(self, row: int) -> dict:
        def _text(col: int) -> str:
            item = self.steps_table.item(row, col)
            return item.text().strip() if item else ""

        duration = None
        dur_str = _text(2)
        if dur_str:
            try:
                duration = float(dur_str)
            except ValueError:
                duration = None

        return {
            "step": row + 1,
            "content": _text(1),
            "duration_minutes": duration,
            "tips": _text(3),
        }
