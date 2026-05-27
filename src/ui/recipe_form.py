# src/ui/recipe_form.py
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGridLayout,
    QScrollArea,
    QSplitter,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHeaderView,
    QGroupBox,
    QLabel,
    QSizePolicy,
    QCompleter,
    QMessageBox,
    QTextEdit,
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
STEP_COLUMNS = ["描述", "用时(分钟)", "备注"]
TIP_COLUMNS = ["内容"]


# ---------------------------------------------------------------------------
# RecipeForm
# ---------------------------------------------------------------------------


class RecipeForm(QWidget):
    """Scrollable form for editing a single recipe."""

    save_requested = Signal(dict)  # emitted when user clicks Save
    dirty_changed = Signal(bool)   # emitted when dirty state changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dirty = False
        self._im = None  # IngredientManager reference
        self._um = None  # UnitManager reference
        self._fm = None  # FileManager reference
        self._source_path: str | None = None
        self._approx_values = {}  # row_id -> {2: text, 3: unit_text, 4: min, 5: max}
        self._build_ui()
        self._connect_change_signals()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Build all groups first
        self._add_basic_info_section()
        self._add_ingredients_section()
        self._add_steps_section()
        self._add_tips_section()
        self._add_images_section()
        self._add_description_section()
        self._add_bottom_buttons()

        # --- layout ---
        # Top: basic info (fixed height)
        outer.addWidget(self._basic_group)

        # Middle: vertical splitter for Ingredients : Steps : [Tips+Images+Description]
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.setChildrenCollapsible(False)
        main_splitter.addWidget(self._ingredients_group)
        main_splitter.addWidget(self._steps_group)

        # Bottom row: tips + images + description side by side
        bottom_row = QSplitter(Qt.Orientation.Horizontal)
        bottom_row.setChildrenCollapsible(False)
        bottom_row.addWidget(self._tips_group)
        bottom_row.addWidget(self._images_group)
        bottom_row.addWidget(self._description_group)

        main_splitter.addWidget(bottom_row)

        # Height ratio: Ingredients=2, Steps=2, Bottom=1
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 2)
        main_splitter.setStretchFactor(2, 1)

        outer.addWidget(main_splitter)
        outer.addWidget(self._buttons_widget)

    # --- Basic info -------------------------------------------------------

    def _add_basic_info_section(self):
        self._basic_group = QGroupBox("基本信息")
        grid = QGridLayout(self._basic_group)
        for c in (1, 3, 5):
            grid.setColumnStretch(c, 2)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("菜谱名称")
        grid.addWidget(self._label("名称:"), 0, 0)
        grid.addWidget(self.name_edit, 0, 1)

        self.difficulty_combo = QComboBox()
        self.difficulty_combo.addItems(DIFFICULTY_OPTIONS)
        self.difficulty_combo.setEditable(True)
        grid.addWidget(self._label("难度:"), 0, 2)
        grid.addWidget(self.difficulty_combo, 0, 3)

        self.category_combo = QComboBox()
        self.category_combo.addItems(CATEGORY_OPTIONS)
        self.category_combo.setEditable(True)
        grid.addWidget(self._label("分类:"), 0, 4)
        grid.addWidget(self.category_combo, 0, 5)

        self.servings_spin = QSpinBox()
        self.servings_spin.setRange(1, 9999)
        self.servings_spin.setValue(1)
        grid.addWidget(self._label("份量:"), 0, 6)
        grid.addWidget(self.servings_spin, 0, 7)

    @staticmethod
    def _label(text: str) -> QLabel:
        """Create a right-aligned label."""
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return lbl

    # --- Images ------------------------------------------------------------

    IMAGE_COLUMNS = ["URL"]

    def _add_images_section(self):
        self._images_group = QGroupBox("图片")
        vbox = QVBoxLayout(self._images_group)

        btn_row = QHBoxLayout()
        self.import_images_btn = QPushButton("快速导入")
        self.import_images_btn.setToolTip("从 MD 文件中提取图片链接并导入")
        self.add_image_btn = QPushButton("添加图片")
        self.remove_image_btn = QPushButton("删除选中")
        btn_row.addWidget(self.import_images_btn)
        btn_row.addWidget(self.add_image_btn)
        btn_row.addWidget(self.remove_image_btn)
        btn_row.addStretch()
        vbox.addLayout(btn_row)

        self.images_table = QTableWidget(0, len(self.IMAGE_COLUMNS))
        self.images_table.setHorizontalHeaderLabels(self.IMAGE_COLUMNS)
        header = self.images_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.images_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectItems
        )
        self.images_table.setSelectionMode(
            QTableWidget.SelectionMode.ExtendedSelection
        )
        self.images_table.setEditTriggers(
            QTableWidget.EditTrigger.CurrentChanged
            | QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.EditKeyPressed
        )
        self.images_table.setMinimumHeight(60)
        vbox.addWidget(self.images_table)

        self.add_image_btn.clicked.connect(self._add_image_row)
        self.remove_image_btn.clicked.connect(self._remove_image_row)
        self.import_images_btn.clicked.connect(self._import_images_from_file)

    # --- Description ---------------------------------------------------------

    def _add_description_section(self):
        self._description_group = QGroupBox("简介")
        vbox = QVBoxLayout(self._description_group)

        btn_row = QHBoxLayout()
        self.import_description_btn = QPushButton("快速导入")
        self.import_description_btn.setToolTip("从 MD 文件中导入简介（H1 标题下的纯文本，自动排除难度和卡路里信息）")
        btn_row.addWidget(self.import_description_btn)
        btn_row.addStretch()
        vbox.addLayout(btn_row)

        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("菜谱介绍...")
        self.description_edit.setMinimumHeight(60)
        vbox.addWidget(self.description_edit)

        self.import_description_btn.clicked.connect(self._import_description_from_file)

    def _add_image_row(self, url: str = ""):
        row = self.images_table.rowCount()
        self.images_table.insertRow(row)
        self.images_table.setItem(row, 0, QTableWidgetItem(url))

    def _remove_image_row(self):
        rows = sorted(
            set(idx.row() for idx in self.images_table.selectedIndexes()),
            reverse=True,
        )
        for r in rows:
            self.images_table.removeRow(r)

    def _collect_images(self) -> list[str]:
        urls = []
        for row in range(self.images_table.rowCount()):
            item = self.images_table.item(row, 0)
            if item:
                url = item.text().strip()
                if url:
                    urls.append(url)
        return urls

    # --- Ingredients ------------------------------------------------------

    def _add_ingredients_section(self):
        self._ingredients_group = QGroupBox("食材")
        vbox = QVBoxLayout(self._ingredients_group)

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
        self.clear_ingredient_qty_btn = QPushButton("清空用量")
        self.clear_ingredient_qty_btn.setToolTip("清空所有食材的数量、范围和备注")
        btn_row.addWidget(self.add_ingredient_btn)
        btn_row.addWidget(self.remove_ingredient_btn)
        btn_row.addWidget(self.clear_ingredient_qty_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.ingredient_up_btn)
        btn_row.addWidget(self.ingredient_down_btn)
        vbox.addLayout(btn_row)

        # Table
        self.ingredients_table = QTableWidget(0, len(INGREDIENT_COLUMNS))
        self.ingredients_table.setHorizontalHeaderLabels(INGREDIENT_COLUMNS)
        header = self.ingredients_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
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
        self.clear_ingredient_qty_btn.clicked.connect(self._clear_ingredient_quantities)
        self.ingredient_up_btn.clicked.connect(lambda: self._move_row(self.ingredients_table, -1))
        self.ingredient_down_btn.clicked.connect(lambda: self._move_row(self.ingredients_table, 1))

    def _add_ingredient_row(self):
        row = self.ingredients_table.rowCount()
        self.ingredients_table.insertRow(row)
        # 数量 (col 2)
        self.ingredients_table.setItem(row, 2, QTableWidgetItem(""))
        # Unit combo box (col 3) — default to g/克
        self.ingredients_table.setCellWidget(row, 3, self._create_unit_combo("g"))
        # 范围(最小) (col 4)
        self.ingredients_table.setItem(row, 4, QTableWidgetItem(""))
        # 范围(最大) (col 5)
        self.ingredients_table.setItem(row, 5, QTableWidgetItem(""))
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

    def _clear_ingredient_quantities(self):
        """清空所有食材的数量、范围、用量描述和备注。"""
        for row in range(self.ingredients_table.rowCount()):
            for col in (2, 4, 5, 8):
                item = self.ingredients_table.item(row, col)
                if item:
                    self.ingredients_table.blockSignals(True)
                    item.setText("")
                    self.ingredients_table.blockSignals(False)
            # 重置用量描述为精确（空选项）
            combo = self.ingredients_table.cellWidget(row, 6)
            if isinstance(combo, QComboBox):
                combo.blockSignals(True)
                combo.setCurrentIndex(0)
                combo.blockSignals(False)
        self._set_dirty(True)

    # --- Steps ------------------------------------------------------------

    def _add_steps_section(self):
        self._steps_group = QGroupBox("步骤")
        vbox = QVBoxLayout(self._steps_group)

        # Buttons row
        btn_row = QHBoxLayout()
        self.add_step_btn = QPushButton("添加步骤")
        self.remove_step_btn = QPushButton("删除选中")
        self.import_steps_btn = QPushButton("快速导入")
        self.import_steps_btn.setToolTip("从 MD 文件导入步骤（每行一条，覆盖已有数据）")
        self.step_up_btn = QPushButton("▲")
        self.step_up_btn.setFixedWidth(30)
        self.step_up_btn.setToolTip("上移")
        self.step_down_btn = QPushButton("▼")
        self.step_down_btn.setFixedWidth(30)
        self.step_down_btn.setToolTip("下移")
        btn_row.addWidget(self.add_step_btn)
        btn_row.addWidget(self.remove_step_btn)
        btn_row.addWidget(self.import_steps_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.step_up_btn)
        btn_row.addWidget(self.step_down_btn)
        vbox.addLayout(btn_row)

        # Table
        self.steps_table = QTableWidget(0, len(STEP_COLUMNS))
        self.steps_table.setHorizontalHeaderLabels(STEP_COLUMNS)
        header = self.steps_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
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
        self.import_steps_btn.clicked.connect(self._import_steps_from_file)
        self.step_up_btn.clicked.connect(lambda: self._move_row(self.steps_table, -1))
        self.step_down_btn.clicked.connect(lambda: self._move_row(self.steps_table, 1))

    def _add_step_row(self):
        row = self.steps_table.rowCount()
        self.steps_table.insertRow(row)

    def _remove_step_row(self):
        rows = sorted(
            set(idx.row() for idx in self.steps_table.selectedIndexes()),
            reverse=True,
        )
        for r in rows:
            self.steps_table.removeRow(r)

    # --- Tips -------------------------------------------------------------

    def _add_tips_section(self):
        self._tips_group = QGroupBox("小贴士")
        vbox = QVBoxLayout(self._tips_group)

        # Buttons row
        btn_row = QHBoxLayout()
        self.add_tip_btn = QPushButton("添加")
        self.remove_tip_btn = QPushButton("删除选中")
        self.import_tips_btn = QPushButton("快速导入")
        self.import_tips_btn.setToolTip("从 MD 文件导入小贴士（每行一条，覆盖已有数据）")
        self.tip_up_btn = QPushButton("▲")
        self.tip_up_btn.setFixedWidth(30)
        self.tip_up_btn.setToolTip("上移")
        self.tip_down_btn = QPushButton("▼")
        self.tip_down_btn.setFixedWidth(30)
        self.tip_down_btn.setToolTip("下移")
        self.clear_all_tips_btn = QPushButton("清空全部")
        self.clear_all_tips_btn.setToolTip("一键清空所有小贴士")
        btn_row.addWidget(self.add_tip_btn)
        btn_row.addWidget(self.remove_tip_btn)
        btn_row.addWidget(self.import_tips_btn)
        btn_row.addWidget(self.clear_all_tips_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.tip_up_btn)
        btn_row.addWidget(self.tip_down_btn)
        vbox.addLayout(btn_row)

        # Table
        self.tips_table = QTableWidget(0, len(TIP_COLUMNS))
        self.tips_table.setHorizontalHeaderLabels(TIP_COLUMNS)
        header = self.tips_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
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
        self.import_tips_btn.clicked.connect(self._import_tips_from_file)
        self.clear_all_tips_btn.clicked.connect(self._clear_all_tips)
        self.tip_up_btn.clicked.connect(lambda: self._move_row(self.tips_table, -1))
        self.tip_down_btn.clicked.connect(lambda: self._move_row(self.tips_table, 1))

    def _add_tip_row(self):
        row = self.tips_table.rowCount()
        self.tips_table.insertRow(row)

    def _remove_tip_row(self):
        rows = sorted(
            set(idx.row() for idx in self.tips_table.selectedIndexes()),
            reverse=True,
        )
        for r in rows:
            self.tips_table.removeRow(r)

    def _clear_all_tips(self):
        """一键清空所有小贴士。"""
        self.tips_table.setRowCount(0)
        self._set_dirty(True)

    # --- Quick Import from file ---------------------------------------------

    @staticmethod
    def _strip_list_marker(line: str) -> str:
        """Remove list markers and Markdown inline formatting, keeping plain text."""
        import re
        # Strip list markers (with optional leading whitespace)
        text = re.sub(r"^\s*(?:\d+[.、．)\s]\s*|[-*•]\s*)", "", line).strip()
        # Strip Markdown inline formatting (order matters)
        text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)          # ![alt](url) → remove
        text = re.sub(r"\[([^\]]*)\]\(([^)]*)\)", r"\1(\2)", text) # [text](url) → text(url)
        text = re.sub(r"`{3}.*?`{3}", "", text, flags=re.DOTALL) # ```code block```
        text = re.sub(r"`([^`]+)`", r"\1", text)                 # `code` → code
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)             # **bold** → bold
        text = re.sub(r"__(.+?)__", r"\1", text)                 # __bold__ → bold
        text = re.sub(r"\*(.+?)\*", r"\1", text)                 # *italic* → italic
        text = re.sub(r"_(.+?)_", r"\1", text)                   # _italic_ → italic
        text = re.sub(r"~~(.+?)~~", r"\1", text)                 # ~~strike~~ → strike
        return text.strip()

    @staticmethod
    def _get_section(content: str, header: str) -> str:
        """Extract content under a ## header from markdown."""
        import re
        sections = re.split(r"^##\s+", content, flags=re.MULTILINE)
        for sec in sections:
            if sec.strip().startswith(header):
                body = sec[len(header):].strip()
                next_h2 = re.search(r"^##\s+", body, re.MULTILINE)
                if next_h2:
                    body = body[: next_h2.start()]
                return body
        return ""

    TIP_FILTER_PATTERNS = [
        "如果您遵循本指南",  # HowToCook boilerplate about issues/PRs
    ]

    def _import_steps_from_file(self):
        """Import steps from '操作' section of current source MD. Overwrites existing data."""
        if not self._source_path or not self._fm:
            QMessageBox.warning(self, "快速导入", "请先选择一个源 MD 文件。")
            return
        try:
            content = self._fm.load_markdown(self._source_path)
            section = self._get_section(content, "操作")
            if not section:
                QMessageBox.information(self, "导入步骤", "未找到「操作」部分。")
                return
            lines = [self._strip_list_marker(line) for line in section.splitlines()]
            lines = [line for line in lines if line]
            if not lines:
                QMessageBox.information(self, "导入步骤", "未找到有效步骤。")
                return
            self.steps_table.setRowCount(0)
            for line in lines:
                self._add_step_row()
                row = self.steps_table.rowCount() - 1
                self.steps_table.setItem(row, 0, QTableWidgetItem(line))
            self._set_dirty(True)
        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"无法读取文件: {e}")

    def _import_tips_from_file(self):
        """Import tips from '附加内容' section of current source MD. Overwrites existing data."""
        if not self._source_path or not self._fm:
            QMessageBox.warning(self, "快速导入", "请先选择一个源 MD 文件。")
            return
        try:
            content = self._fm.load_markdown(self._source_path)
            section = self._get_section(content, "附加内容")
            if not section:
                QMessageBox.information(self, "导入小贴士", "未找到「附加内容」部分。")
                return
            lines = [self._strip_list_marker(line) for line in section.splitlines()]
            lines = [
                line for line in lines
                if line and not any(p in line for p in self.TIP_FILTER_PATTERNS)
            ]
            if not lines:
                QMessageBox.information(self, "导入小贴士", "未找到有效小贴士。")
                return
            self.tips_table.setRowCount(0)
            for line in lines:
                self._add_tip_row()
                row = self.tips_table.rowCount() - 1
                self.tips_table.setItem(row, 0, QTableWidgetItem(line))
            self._set_dirty(True)
        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"无法读取文件: {e}")

    DESCRIPTION_FILTER_PATTERNS = [
        "预估烹饪难度",
        "预估卡路里",
    ]

    def _import_description_from_file(self):
        """Import description from plain text directly under the h1 heading."""
        if not self._source_path or not self._fm:
            QMessageBox.warning(self, "快速导入", "请先选择一个源 MD 文件。")
            return
        try:
            content = self._fm.load_markdown(self._source_path)
            lines = content.splitlines()
            description_lines = []
            found_h1 = False
            for line in lines:
                if line.startswith("# "):
                    found_h1 = True
                    continue
                if found_h1:
                    if line.startswith("#"):
                        break
                    stripped = line.strip()
                    if stripped and stripped.startswith("!"):
                        continue  # skip image markdown lines
                    if stripped and not any(p in stripped for p in self.DESCRIPTION_FILTER_PATTERNS):
                        description_lines.append(stripped)
                    elif not stripped and description_lines:
                        description_lines.append("")
            text = "\n".join(description_lines).strip()
            if not text:
                QMessageBox.information(self, "导入简介", "未找到有效简介内容。")
                return
            self.description_edit.setPlainText(text)
            self._set_dirty(True)
        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"无法读取文件: {e}")

    def _import_images_from_file(self):
        """从 MD 文件中提取图片链接并导入到 out/images。

        1. 提取 MD 中所有图片链接
        2. 清理现有图片记录（文件不存在则删除）
        3. 对比文件 hash，复用已存在的图片或复制新图片
        4. 智能合并：保留有效现有图片，新图片追加到末尾
        """
        from src.managers.image_manager import ImageManager

        if not self._source_path or not self._fm:
            QMessageBox.warning(self, "快速导入", "请先选择一个源 MD 文件。")
            return
        try:
            content = self._fm.load_markdown(self._source_path)
            image_urls = ImageManager.extract_image_urls(content)
            if not image_urls:
                QMessageBox.information(self, "导入图片", "MD 文件中未找到图片链接。")
                return

            recipe_name = self.name_edit.text().strip()
            if not recipe_name:
                QMessageBox.warning(self, "导入图片", "请先输入菜谱名称。")
                return

            existing_images = self._collect_images()

            im = ImageManager()
            final_images, new_images = im.import_images(
                recipe_name=recipe_name,
                md_image_urls=image_urls,
                md_source_path=self._source_path,
                source_dir=self._fm.source_dir,
                output_dir=self._fm.output_dir,
                existing_images=existing_images,
            )

            # Clear and repopulate the images table
            self.images_table.setRowCount(0)
            for url in final_images:
                self._add_image_row(url)

            if new_images:
                QMessageBox.information(
                    self, "导入图片",
                    f"成功导入 {len(new_images)} 张图片。\n"
                    f"总计: {len(final_images)} 张。"
                )
            else:
                QMessageBox.information(
                    self, "导入图片",
                    f"所有图片已存在，未新增图片。\n"
                    f"总计: {len(final_images)} 张。"
                )
            self._set_dirty(True)
        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"无法导入图片: {e}")

    # --- Bottom buttons ---------------------------------------------------

    def _add_bottom_buttons(self):
        self._buttons_widget = QWidget()
        row = QHBoxLayout(self._buttons_widget)
        row.setContentsMargins(0, 0, 0, 0)
        self.save_btn = QPushButton("保存")
        self.clear_btn = QPushButton("清空")
        row.addWidget(self.save_btn)
        row.addWidget(self.clear_btn)
        row.addStretch()

        self.save_btn.clicked.connect(self._on_save_clicked)
        self.clear_btn.clicked.connect(self.clear_form)

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
        self.images_table.cellChanged.connect(self._mark_dirty)
        self.ingredients_table.cellChanged.connect(self._on_ingredient_cell_changed)
        self.steps_table.cellChanged.connect(self._on_step_cell_changed)
        self.tips_table.cellChanged.connect(self._on_tip_cell_changed)

        self.description_edit.textChanged.connect(self._mark_dirty)

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
        self._set_dirty(True)
        # Skip non-text columns: 1 (link, non-editable), 6 (用量描述 combo), 7 (可选 checkbox)
        if col not in (1, 6, 7):
            self._clean_cell(self.ingredients_table, row, col)
        if col == 0:
            self._update_link_status(row)

    def _on_step_cell_changed(self, row: int, col: int):
        self._set_dirty(True)
        self._clean_cell(self.steps_table, row, col)

    def _on_tip_cell_changed(self, row: int, col: int):
        self._set_dirty(True)
        self._clean_cell(self.tips_table, row, col)

    def _mark_dirty(self, *_):
        self._set_dirty(True)

    def _set_dirty(self, dirty: bool):
        """Set dirty state and emit signal on change."""
        if self._dirty != dirty:
            self._dirty = dirty
            self.dirty_changed.emit(dirty)

    def _move_row(self, table: QTableWidget, direction: int):
        """Move the current row up (direction=-1) or down (direction=+1)."""
        row = table.currentRow()
        if row < 0:
            return
        target = row + direction
        if target < 0 or target >= table.rowCount():
            return

        table.blockSignals(True)

        is_ing = table is self.ingredients_table
        gray = Qt.GlobalColor.gray
        black = Qt.GlobalColor.black

        # --- Step 1: restore hidden approx values so collect captures real data ---
        if is_ing:
            for r in (row, target):
                key = self._get_approx_key(r)
                saved = self._approx_values.pop(key, None)
                if saved is None:
                    continue
                for col in (2, 4, 5):
                    item = table.item(r, col)
                    if item:
                        if saved.get(col):
                            item.setText(saved[col])
                        item.setForeground(black)
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                uc = table.cellWidget(r, 3)
                if isinstance(uc, QComboBox):
                    uc.setEnabled(True)
                    uc.setStyleSheet("")
                    if saved.get(3):
                        idx = uc.findText(saved[3])
                        if idx >= 0:
                            uc.setCurrentIndex(idx)
                        else:
                            uc.setEditText(saved[3])

        # --- Step 2: collect data from both rows ---
        def collect_row(r):
            items = {}
            combos = {}
            for col in range(table.columnCount()):
                item = table.item(r, col)
                if item is not None:
                    items[col] = (
                        item.text(), item.foreground(), item.flags(),
                        item.data(Qt.ItemDataRole.UserRole),
                        item.checkState(),
                    )
                w = table.cellWidget(r, col)
                if w is not None and isinstance(w, QComboBox):
                    combos[col] = (
                        w.isEditable(),
                        w.isEnabled(),
                        w.styleSheet(),
                        [w.itemText(i) for i in range(w.count())],
                        w.currentIndex(),
                        w.currentText(),
                    )
            return items, combos

        src_data = collect_row(row)
        dst_data = collect_row(target)

        # --- Step 3: write swapped data ---
        def write_row(r, items, combos):
            table.setRowCount(max(table.rowCount(), r + 1))
            for col in range(table.columnCount()):
                table.setItem(r, col, None)
                table.removeCellWidget(r, col)
                if col in items:
                    text, fg, flags, user_data, check_state = items[col]
                    new_item = QTableWidgetItem(text)
                    new_item.setForeground(fg)
                    new_item.setFlags(flags)
                    if user_data is not None:
                        new_item.setData(Qt.ItemDataRole.UserRole, user_data)
                    if col == 7:
                        new_item.setCheckState(check_state)
                    table.setItem(r, col, new_item)
                if col in combos:
                    editable, enabled, stylesheet, options, cur_idx, cur_text = combos[col]
                    combo = QComboBox()
                    combo.setEditable(False)  # unit combos are not editable
                    combo.addItems(options)
                    if col == 6:
                        combo.currentIndexChanged.connect(
                            lambda _=None, cb=combo: self._on_qty_desc_changed(cb)
                        )
                    else:
                        combo.currentIndexChanged.connect(self._mark_dirty)
                    idx = combo.findText(cur_text)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                    # Always write combos in normal state; visual is applied in step 4
                    combo.setEnabled(True)
                    combo.setStyleSheet("")
                    table.setCellWidget(r, col, combo)

        write_row(row, dst_data[0], dst_data[1])
        write_row(target, src_data[0], src_data[1])

        # --- Step 4: re-apply link status and approximate visual state ---
        if is_ing:
            for r in (row, target):
                self._update_link_status(r)
                self._update_approx_state(r)

        table.blockSignals(False)
        table.selectRow(target)
        self._set_dirty(True)

    def is_dirty(self) -> bool:
        """Return whether the form has unsaved changes."""
        return self._dirty

    def set_clean(self):
        """Mark the form as having no unsaved changes."""
        if self._dirty:
            self._dirty = False
            self.dirty_changed.emit(False)

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
        self._set_dirty(False)  # clear_form triggers change signals; reset after

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

        # Images
        self.description_edit.setPlainText(data.get("description", ""))
        for url in data.get("images", []):
            self._add_image_row(url)

        # Ingredients
        for ing in data.get("ingredients", []):
            self._add_ingredient_row_from(ing)

        # Steps
        for step in data.get("steps", []):
            self._add_step_row_from(step)

        # Tips
        tips = data.get("tips", [])
        for tip in tips:
            self._add_tip_row_from(tip)

        self._set_dirty(False)  # reset after all fields are populated
        self._resize_columns_to_content()

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
            item = self.tips_table.item(row, 0)
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
            "images": self._collect_images(),
            "description": self.description_edit.toPlainText().strip(),
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
        self.images_table.setRowCount(0)
        self.description_edit.clear()
        self.ingredients_table.setRowCount(0)
        self.steps_table.setRowCount(0)
        self.tips_table.setRowCount(0)
        self._set_dirty(False)

    def _resize_columns_to_content(self):
        """Set column widths based on content, then switch to interactive for manual drag."""
        self._fit_table(self.ingredients_table, {
            1: 40,  # 关联 - narrow
            7: 60,  # 是否可选 - narrow
            8: 150, # 备注 - wider default
        }, stretch_cols=[0, 2, 3, 4, 5, 6, 8])

        self._fit_table(self.steps_table, {
            1: 80,  # 用时 - narrow
        }, stretch_cols=[0, 2])

        self._fit_table(self.tips_table, {}, stretch_cols=[0])
        self._fit_table(self.images_table, {}, stretch_cols=[0])

    def _fit_table(self, table, narrow_widths, stretch_cols):
        """Auto-size columns, then switch all to Interactive for manual drag."""
        from PySide6.QtWidgets import QApplication
        header = table.horizontalHeader()

        # Narrow columns get fixed widths
        for col, w in narrow_widths.items():
            header.resizeSection(col, w)

        # Stretch columns auto-size to content
        for col in stretch_cols:
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        # Let Qt process layout
        QApplication.processEvents()

        # For single-stretch tables, make the one column fill remaining width
        if len(stretch_cols) == 1:
            c = stretch_cols[0]
            used = sum(header.sectionSize(i) for i in range(table.columnCount()) if i != c)
            avail = table.viewport().width() - used
            if avail > header.sectionSize(c):
                header.resizeSection(c, avail)

        # Switch all to interactive for manual dragging
        for col in range(table.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)

    def set_ingredient_manager(self, mgr):
        """Set the ingredient manager for auto-completion and linking."""
        self._im = mgr
        self._update_completer()

    def set_unit_manager(self, mgr):
        """Set the unit manager for unit dropdown population."""
        self._um = mgr
        self._refresh_unit_combos()

    def set_file_source(self, source_path: str, fm):
        """Set the current source MD path and file manager for quick import."""
        self._source_path = source_path
        self._fm = fm

    def _create_unit_combo(self, selected: str = "") -> QComboBox:
        """Create a QComboBox for the unit column."""
        combo = QComboBox()
        combo.setEditable(False)
        if self._um:
            combo.addItems(self._um.get_display_names())
        if selected:
            name = selected
            if self._um:
                unit = self._um.get_by_name(selected)
                if unit:
                    name = unit.name
            idx = combo.findText(name)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.currentIndexChanged.connect(self._mark_dirty)
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
        # Always search the table to find the current row — the cached property
        # can be stale after row deletion or reordering.
        row = None
        for r in range(self.ingredients_table.rowCount()):
            if self.ingredients_table.cellWidget(r, 6) is combo:
                row = r
                break
        if row is not None:
            self._update_approx_state(row)

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
                    # Resolve old value to current primary name via alias index
                    if current:
                        unit = self._um.get_by_name(current)
                        resolved = unit.name if unit else current
                        idx = combo.findText(resolved)
                        if idx >= 0:
                            combo.setCurrentIndex(idx)
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
        self._set_dirty(True)

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

    def _get_approx_key(self, row: int) -> str:
        """Get a stable storage key for a row's approx values."""
        # Use a persistent ID stored as property on the row's name item
        name_item = self.ingredients_table.item(row, 0)
        if name_item is None:
            return f"row_{row}"
        uid = name_item.data(Qt.ItemDataRole.UserRole)
        if uid is None:
            uid = f"row_{id(name_item)}"
            name_item.setData(Qt.ItemDataRole.UserRole, uid)
        return uid

    def _update_approx_state(self, row: int):
        """When '用量描述' is set, hide quantity/range/unit cells and save their values."""
        combo = self.ingredients_table.cellWidget(row, 6)
        # Keep the row property in sync so signal handlers can locate the row
        if isinstance(combo, QComboBox):
            combo.setProperty("_ingredient_row", row)
        is_approx = isinstance(combo, QComboBox) and combo.currentText() != ""
        gray = Qt.GlobalColor.gray
        black = Qt.GlobalColor.black
        key = self._get_approx_key(row)

        if is_approx:
            # Save current values before hiding
            if key not in self._approx_values:
                saved = {}
                for col in (2, 4, 5):
                    item = self.ingredients_table.item(row, col)
                    saved[col] = item.text() if item else ""
                    self.ingredients_table.blockSignals(True)
                    item.setText("")
                    self.ingredients_table.blockSignals(False)
                unit_combo = self.ingredients_table.cellWidget(row, 3)
                saved[3] = unit_combo.currentText() if isinstance(unit_combo, QComboBox) else ""
                self._approx_values[key] = saved
        else:
            # Restore saved values
            saved = self._approx_values.pop(key, None)
            if saved:
                for col in (2, 4, 5):
                    item = self.ingredients_table.item(row, col)
                    if item and saved.get(col):
                        self.ingredients_table.blockSignals(True)
                        item.setText(saved[col])
                        self.ingredients_table.blockSignals(False)
                if saved.get(3):
                    unit_combo = self.ingredients_table.cellWidget(row, 3)
                    if isinstance(unit_combo, QComboBox):
                        self.ingredients_table.blockSignals(True)
                        idx = unit_combo.findText(saved[3])
                        if idx >= 0:
                            unit_combo.setCurrentIndex(idx)
                        else:
                            unit_combo.setEditText(saved[3])
                        self.ingredients_table.blockSignals(False)

        # Update visual state (always, regardless of save/restore)
        for col in (2, 4, 5):
            item = self.ingredients_table.item(row, col)
            if item is None:
                continue
            self.ingredients_table.blockSignals(True)
            if is_approx:
                item.setForeground(gray)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            else:
                item.setForeground(black)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.ingredients_table.blockSignals(False)

        unit_combo = self.ingredients_table.cellWidget(row, 3)
        if isinstance(unit_combo, QComboBox):
            self.ingredients_table.blockSignals(True)
            if is_approx:
                unit_combo.setEnabled(False)
                unit_combo.setStyleSheet("color: gray;")
            else:
                unit_combo.setEnabled(True)
                unit_combo.setStyleSheet("")
            self.ingredients_table.blockSignals(False)

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
        if ing.get("quantity_description"):
            qty_desc = ing["quantity_description"]
        elif ing.get("is_approximate"):
            qty_desc = "适量"
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

        # Apply approximate state if needed
        self._update_approx_state(row)

    def _add_step_row_from(self, step: dict) -> None:
        row = self.steps_table.rowCount()
        self.steps_table.insertRow(row)

        # 描述
        self.steps_table.setItem(row, 0, QTableWidgetItem(step.get("content", "")))

        # 用时(分钟)
        duration = step.get("duration_minutes")
        dur_text = str(duration) if duration is not None else ""
        self.steps_table.setItem(row, 1, QTableWidgetItem(dur_text))

        # 备注
        self.steps_table.setItem(row, 2, QTableWidgetItem(step.get("tips", "")))

    def _add_tip_row_from(self, tip) -> None:
        row = self.tips_table.rowCount()
        self.tips_table.insertRow(row)
        text = tip if isinstance(tip, str) else str(tip)
        self.tips_table.setItem(row, 0, QTableWidgetItem(text))

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
        dur_str = _text(1)
        if dur_str:
            try:
                duration = float(dur_str)
            except ValueError:
                duration = None

        return {
            "content": _text(0),
            "duration_minutes": duration,
            "tips": _text(2),
        }
