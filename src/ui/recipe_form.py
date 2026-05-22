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
    QTextEdit,
    QPushButton,
    QHeaderView,
    QGroupBox,
    QHBoxLayout,
    QSizePolicy,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DIFFICULTY_OPTIONS = ["", "simple", "easy", "medium", "hard", "expert"]
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

INGREDIENT_COLUMNS = ["食材名称", "数量", "单位", "范围(最小)", "范围(最大)", "是否可选", "备注"]
STEP_COLUMNS = ["序号", "描述", "用时(分钟)", "备注"]


# ---------------------------------------------------------------------------
# RecipeForm
# ---------------------------------------------------------------------------


class RecipeForm(QWidget):
    """Scrollable form for editing a single recipe."""

    save_requested = Signal(dict)  # emitted when user clicks Save

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dirty = False
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
        btn_row.addWidget(self.add_ingredient_btn)
        btn_row.addWidget(self.remove_ingredient_btn)
        btn_row.addStretch()
        vbox.addLayout(btn_row)

        # Table
        self.ingredients_table = QTableWidget(0, len(INGREDIENT_COLUMNS))
        self.ingredients_table.setHorizontalHeaderLabels(INGREDIENT_COLUMNS)
        header = self.ingredients_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.ingredients_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.ingredients_table.setMinimumHeight(120)
        self.ingredients_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        vbox.addWidget(self.ingredients_table)

        # Connect buttons
        self.add_ingredient_btn.clicked.connect(self._add_ingredient_row)
        self.remove_ingredient_btn.clicked.connect(self._remove_ingredient_row)

        self._layout.addWidget(group)

    def _add_ingredient_row(self):
        row = self.ingredients_table.rowCount()
        self.ingredients_table.insertRow(row)
        # Default: unchecked optional
        opt_item = QTableWidgetItem()
        opt_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        opt_item.setCheckState(Qt.CheckState.Unchecked)
        self.ingredients_table.setItem(row, 5, opt_item)

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
        btn_row.addWidget(self.add_step_btn)
        btn_row.addWidget(self.remove_step_btn)
        btn_row.addStretch()
        vbox.addLayout(btn_row)

        # Table
        self.steps_table = QTableWidget(0, len(STEP_COLUMNS))
        self.steps_table.setHorizontalHeaderLabels(STEP_COLUMNS)
        header = self.steps_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.steps_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.steps_table.setMinimumHeight(120)
        self.steps_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        vbox.addWidget(self.steps_table)

        # Connect buttons
        self.add_step_btn.clicked.connect(self._add_step_row)
        self.remove_step_btn.clicked.connect(self._remove_step_row)

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

        self.tips_edit = QTextEdit()
        self.tips_edit.setPlaceholderText("每行一条小贴士")
        self.tips_edit.setMaximumHeight(100)
        vbox.addWidget(self.tips_edit)

        self._layout.addWidget(group)

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
        self.ingredients_table.cellChanged.connect(self._mark_dirty)
        self.steps_table.cellChanged.connect(self._mark_dirty)
        self.tips_edit.textChanged.connect(self._mark_dirty)

    def _mark_dirty(self, *_):
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
        idx = self.difficulty_combo.findText(difficulty)
        if idx >= 0:
            self.difficulty_combo.setCurrentIndex(idx)
        else:
            self.difficulty_combo.setEditText(difficulty)

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
        if tips:
            self.tips_edit.setPlainText("\n".join(tips))

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

        tips_text = self.tips_edit.toPlainText().strip()
        tips = [line.strip() for line in tips_text.split("\n") if line.strip()] if tips_text else []

        return {
            "name": self.name_edit.text().strip(),
            "source_file": "",
            "category": self.category_combo.currentText().strip(),
            "difficulty": self.difficulty_combo.currentText().strip(),
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
        self.tips_edit.clear()
        self._dirty = False

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

        # 数量
        quantity = ing.get("quantity")
        qty_text = str(quantity) if quantity is not None else ""
        self.ingredients_table.setItem(row, 1, QTableWidgetItem(qty_text))

        # 单位
        self.ingredients_table.setItem(
            row, 2, QTableWidgetItem(ing.get("unit", ""))
        )

        # 范围(最小)
        qty_range = ing.get("quantity_range")
        range_min = str(qty_range["min"]) if qty_range and "min" in qty_range else ""
        self.ingredients_table.setItem(row, 3, QTableWidgetItem(range_min))

        # 范围(最大)
        range_max = str(qty_range["max"]) if qty_range and "max" in qty_range else ""
        self.ingredients_table.setItem(row, 4, QTableWidgetItem(range_max))

        # 是否可选
        opt_item = QTableWidgetItem()
        opt_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        opt_item.setCheckState(
            Qt.CheckState.Checked if ing.get("is_optional", False)
            else Qt.CheckState.Unchecked
        )
        self.ingredients_table.setItem(row, 5, opt_item)

        # 备注
        self.ingredients_table.setItem(
            row, 6, QTableWidgetItem(ing.get("note", ""))
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

    def _collect_ingredient_row(self, row: int) -> dict:
        def _text(col: int) -> str:
            item = self.ingredients_table.item(row, col)
            return item.text().strip() if item else ""

        name = _text(0)
        qty_str = _text(1)
        unit = _text(2)
        range_min_str = _text(3)
        range_max_str = _text(4)
        opt_item = self.ingredients_table.item(row, 5)
        is_optional = (
            opt_item.checkState() == Qt.CheckState.Checked if opt_item else False
        )
        note = _text(6)

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
            "quantity": quantity,
            "unit": unit,
            "quantity_range": quantity_range,
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
