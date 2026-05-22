# src/ui/merge_dialog.py
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

from src.managers.ingredient_manager import IngredientManager


class MergeDialog(QDialog):
    """Dialog for merging two ingredients into one."""

    def __init__(
        self,
        manager: IngredientManager,
        preselect_a: str | None = None,
        preselect_b: str | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._manager = manager
        self._ingredients = manager.get_all()
        self._names = [ing.name for ing in self._ingredients]
        self._keep_choice: str | None = None

        self.setWindowTitle("合并食材")
        self.setMinimumWidth(480)
        self._setup_ui(preselect_a, preselect_b)

    def _make_combo(self) -> QComboBox:
        """Create an editable combo box with search completer."""
        combo = QComboBox()
        combo.addItems(self._names)
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        completer = QCompleter(self._names)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        combo.setCompleter(completer)
        return combo

    def _setup_ui(self, preselect_a: str | None, preselect_b: str | None) -> None:
        layout = QVBoxLayout(self)

        # --- Ingredient selection ---
        sel_group = QGroupBox("选择食材")
        sel_layout = QVBoxLayout(sel_group)

        # Ingredient A
        row_a = QHBoxLayout()
        row_a.addWidget(QLabel("食材 A:"))
        self._combo_a = self._make_combo()
        row_a.addWidget(self._combo_a, 1)
        sel_layout.addLayout(row_a)

        # Ingredient B
        row_b = QHBoxLayout()
        row_b.addWidget(QLabel("食材 B:"))
        self._combo_b = self._make_combo()
        row_b.addWidget(self._combo_b, 1)
        sel_layout.addLayout(row_b)

        layout.addWidget(sel_group)

        # Pre-select if provided
        if preselect_a:
            idx = self._combo_a.findText(preselect_a)
            if idx >= 0:
                self._combo_a.setCurrentIndex(idx)
        if preselect_b:
            idx = self._combo_b.findText(preselect_b)
            if idx >= 0:
                self._combo_b.setCurrentIndex(idx)

        # --- Keep-as-standard radio ---
        keep_group = QGroupBox("保留标准名称")
        keep_layout = QVBoxLayout(keep_group)

        self._radio_a = QRadioButton()
        self._radio_b = QRadioButton()
        keep_layout.addWidget(self._radio_a)
        keep_layout.addWidget(self._radio_b)

        layout.addWidget(keep_group)

        # --- Preview ---
        preview_group = QGroupBox("合并预览")
        preview_layout = QVBoxLayout(preview_group)

        self._preview_aliases = QLabel("别名: —")
        self._preview_aliases.setWordWrap(True)
        preview_layout.addWidget(self._preview_aliases)

        self._preview_category = QLabel("分类: —")
        preview_layout.addWidget(self._preview_category)

        self._preview_usda = QLabel("USDA 匹配: —")
        preview_layout.addWidget(self._preview_usda)

        layout.addWidget(preview_group)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        self._merge_btn = QPushButton("合并")
        self._merge_btn.clicked.connect(self.accept)
        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(self._merge_btn)
        btn_row.addWidget(self._cancel_btn)
        layout.addLayout(btn_row)

        # --- Signal connections ---
        self._combo_a.currentIndexChanged.connect(self._update_preview)
        self._combo_b.currentIndexChanged.connect(self._update_preview)
        self._radio_a.toggled.connect(self._update_preview)

        # Initial state
        self._update_radio_labels()
        self._radio_a.setChecked(True)
        self._update_preview()

    # -- public API ---------------------------------------------------------

    def get_merge_params(self) -> tuple[str, str]:
        """Return (keep_name, remove_name) based on user selection."""
        name_a = self._combo_a.currentText()
        name_b = self._combo_b.currentText()
        if self._radio_a.isChecked():
            return name_a, name_b
        else:
            return name_b, name_a

    # -- private helpers ----------------------------------------------------

    def _update_radio_labels(self) -> None:
        name_a = self._combo_a.currentText() or "食材 A"
        name_b = self._combo_b.currentText() or "食材 B"
        self._radio_a.setText(f"保留: {name_a}")
        self._radio_b.setText(f"保留: {name_b}")

    def _find_ingredient(self, name: str):
        for ing in self._ingredients:
            if ing.name == name:
                return ing
        return None

    def _update_preview(self) -> None:
        self._update_radio_labels()

        name_a = self._combo_a.currentText()
        name_b = self._combo_b.currentText()

        if not name_a or not name_b:
            return

        ing_a = self._find_ingredient(name_a)
        ing_b = self._find_ingredient(name_b)
        if ing_a is None or ing_b is None:
            return

        keep_ing = ing_a if self._radio_a.isChecked() else ing_b
        remove_ing = ing_b if self._radio_a.isChecked() else ing_a

        # Merged aliases
        all_aliases = set(keep_ing.aliases) | set(remove_ing.aliases)
        all_aliases.discard(keep_ing.name)
        all_aliases.add(remove_ing.name)
        for alias in remove_ing.aliases:
            all_aliases.add(alias)
        aliases_text = ", ".join(sorted(all_aliases)) if all_aliases else "(无)"
        self._preview_aliases.setText(f"别名: {aliases_text}")

        # Category
        self._preview_category.setText(f"分类: {keep_ing.category}")

        # USDA match status
        if keep_ing.usda_match_status == "matched":
            usda_text = f"已匹配 (FDC {keep_ing.usda_id})"
        elif remove_ing.usda_match_status == "matched":
            usda_text = f"将继承匹配 (FDC {remove_ing.usda_id})"
        else:
            usda_text = "未匹配"
        self._preview_usda.setText(f"USDA 匹配: {usda_text}")

        # Validate: same ingredient selected
        if name_a == name_b:
            self._merge_btn.setEnabled(False)
        else:
            self._merge_btn.setEnabled(True)
