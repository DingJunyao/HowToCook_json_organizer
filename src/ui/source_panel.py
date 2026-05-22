# src/ui/source_panel.py
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QTextBrowser,
)


CATEGORY_MAP = {
    "aquatic": "水产",
    "breakfast": "早餐",
    "condiment": "调料",
    "dessert": "甜品",
    "drink": "饮料",
    "meat_dish": "荤菜",
    "semi-finished": "半成品",
    "soup": "汤与粥",
    "staple": "主食",
    "vegetable_dish": "素菜",
}


class SourcePanel(QWidget):
    """Left panel: directory tree + markdown preview."""

    file_selected = Signal(str)  # emits relative path of the selected .md file

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fm = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter()
        splitter.setOrientation(QSplitter.Orientation.Vertical)

        # --- tree ---
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("菜谱目录")
        self.tree.setAnimated(True)
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        splitter.addWidget(self.tree)

        # --- preview ---
        self.preview = QTextBrowser()
        self.preview.setPlaceholderText("双击左侧文件以预览 Markdown 内容")
        splitter.addWidget(self.preview)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_file_manager(self, fm):
        """Set the FileManager and refresh the tree."""
        self._fm = fm
        self.refresh_tree()

    def refresh_tree(self):
        """Rebuild the directory tree from source files."""
        self.tree.clear()
        if self._fm is None:
            return

        # Collect output json filenames (just stem names) for status check
        output_stems = set()
        for p in self._fm.list_output_recipes():
            output_stems.add(p.stem)

        # Collect source files grouped by category
        source_files = self._fm.list_source_files()
        categories: dict[str, list[tuple[str, Path]]] = {}
        for full_path in source_files:
            rel = full_path.relative_to(self._fm.source_dir)
            # rel looks like  dishes/vegetable_dish/炒青菜.md
            parts = rel.parts  # ('dishes', 'vegetable_dish', '炒青菜.md')
            if len(parts) >= 3:
                cat_folder = parts[1]
            else:
                cat_folder = "other"
            categories.setdefault(cat_folder, []).append((str(rel), full_path))

        # Build tree
        for cat_folder in sorted(categories.keys()):
            display_name = CATEGORY_MAP.get(cat_folder, cat_folder)
            cat_item = QTreeWidgetItem(self.tree, [display_name])
            cat_item.setData(0, 100, cat_folder)  # store folder key

            file_entries = sorted(categories[cat_folder], key=lambda x: x[0])
            for rel_path_str, full_path in file_entries:
                file_stem = Path(rel_path_str).stem
                processed = file_stem in output_stems
                label = f"{file_stem} ✓" if processed else file_stem
                file_item = QTreeWidgetItem(cat_item, [label])
                file_item.setData(0, 101, rel_path_str)  # store relative path
                file_item.setData(0, 102, str(full_path))  # store full path

        self.tree.expandAll()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_double_click(self, item: QTreeWidgetItem, _column: int):
        rel_path = item.data(0, 101)
        if rel_path is None:
            return  # clicked a category node

        # Load markdown content into preview
        if self._fm is not None:
            try:
                content = self._fm.load_markdown(rel_path)
                self.preview.setPlainText(content)
            except Exception:
                self.preview.setPlainText(f"[无法加载文件: {rel_path}]")

        self.file_selected.emit(rel_path)
