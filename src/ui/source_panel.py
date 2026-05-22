# src/ui/source_panel.py
from __future__ import annotations

import json
import markdown
from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QTextBrowser,
    QPushButton,
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
    """Left panel: directory tree + markdown preview, with source/output toggle."""

    file_selected = Signal(str)  # emits relative path of the selected .md file
    output_file_selected = Signal(str)  # emits relative path of a JSON output file

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fm = None
        self._mode = "source"  # "source" or "output"
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # --- mode toggle ---
        toggle_bar = QHBoxLayout()
        self.btn_source = QPushButton("源文件")
        self.btn_output = QPushButton("已输出")
        self.btn_source.setCheckable(True)
        self.btn_output.setCheckable(True)
        self.btn_source.setChecked(True)

        self.btn_source.clicked.connect(lambda: self._set_mode("source"))
        self.btn_output.clicked.connect(lambda: self._set_mode("output"))
        self._update_toggle_style()

        toggle_bar.addWidget(self.btn_source)
        toggle_bar.addWidget(self.btn_output)
        layout.addLayout(toggle_bar)

        # --- splitter ---
        splitter = QSplitter()
        splitter.setOrientation(Qt.Orientation.Vertical)

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

    def _set_mode(self, mode: str):
        """Switch between 'source' and 'output' modes."""
        self._mode = mode
        self.btn_source.setChecked(mode == "source")
        self.btn_output.setChecked(mode == "output")
        self._update_toggle_style()
        self.refresh_tree()

    def _update_toggle_style(self):
        """Apply visual feedback to the active toggle button."""
        active = (
            "background-color: #4a9eff; color: white; font-weight: bold; "
            "border: 1px solid #3a8eef; border-radius: 3px; padding: 4px 12px;"
        )
        inactive = (
            "background-color: #f0f0f0; color: #333; "
            "border: 1px solid #ccc; border-radius: 3px; padding: 4px 12px;"
        )
        self.btn_source.setStyleSheet(active if self._mode == "source" else inactive)
        self.btn_output.setStyleSheet(active if self._mode == "output" else inactive)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_file_manager(self, fm):
        """Set the FileManager and refresh the tree."""
        self._fm = fm
        self.refresh_tree()

    def render_markdown(self, text: str):
        """Render markdown text as HTML in the preview area."""
        self._render_markdown(text)

    def _render_markdown(self, text: str):
        """Internal: convert markdown to HTML and display."""
        html = markdown.markdown(text, extensions=["tables", "fenced_code"])
        styled = f"""
        <html><head><style>
        body {{ font-family: "Microsoft YaHei", "Segoe UI", sans-serif; font-size: 14px;
               padding: 8px; line-height: 1.6; }}
        h1 {{ color: #2c3e50; border-bottom: 1px solid #ddd; padding-bottom: 4px; }}
        h2 {{ color: #34495e; margin-top: 16px; }}
        ul {{ padding-left: 20px; }}
        li {{ margin: 2px 0; }}
        </style></head><body>{html}</body></html>
        """
        self.preview.setHtml(styled)

    def refresh_tree(self):
        """Rebuild the directory tree based on current mode."""
        self.tree.clear()
        if self._fm is None:
            return

        if self._mode == "source":
            self._refresh_source_tree()
        else:
            self._refresh_output_tree()

    def update_parse_status(self, results: dict):
        """Update existing tree items with parse status icons.

        Args:
            results: dict mapping relative_path -> status_string.
                     status_string is one of: "processed", "parsed", "error".
        """
        status_icons = {
            "processed": "✓",
            "parsed": "○",
            "error": "⚠",
        }
        # Build a lookup from relative_path to its tree item
        for i in range(self.tree.topLevelItemCount()):
            cat_item = self.tree.topLevelItem(i)
            for j in range(cat_item.childCount()):
                file_item = cat_item.child(j)
                rel_path = file_item.data(0, 101)
                if rel_path is None:
                    continue
                status = results.get(rel_path)
                if status is None:
                    continue
                icon = status_icons.get(status, "")
                file_stem = Path(rel_path).stem
                file_item.setText(0, f"{file_stem} {icon}")

    # ------------------------------------------------------------------
    # Tree builders
    # ------------------------------------------------------------------

    def _refresh_source_tree(self):
        """Build tree from source MD files (original behavior)."""
        fm = self._fm

        # Collect output json filenames (just stem names) for status check
        output_stems = set()
        for p in fm.list_output_recipes():
            output_stems.add(p.stem)

        # Collect source files grouped by category
        source_files = fm.list_source_files()
        categories: dict[str, list[tuple[str, Path]]] = {}
        for full_path in source_files:
            rel = full_path.relative_to(fm.source_dir)
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
            cat_item.setData(0, 100, cat_folder)

            file_entries = sorted(categories[cat_folder], key=lambda x: x[0])
            for rel_path_str, full_path in file_entries:
                file_stem = Path(rel_path_str).stem
                processed = file_stem in output_stems
                label = f"{file_stem} ✓" if processed else file_stem
                file_item = QTreeWidgetItem(cat_item, [label])
                file_item.setData(0, 101, rel_path_str)
                file_item.setData(0, 102, str(full_path))

        self.tree.expandAll()

    def _refresh_output_tree(self):
        """Build tree from output JSON files."""
        fm = self._fm
        output_files = fm.list_output_recipes()

        if not output_files:
            item = QTreeWidgetItem(self.tree, ["(无已输出的 JSON 文件)"])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            return

        for json_path in output_files:
            stem = json_path.stem
            label = stem
            file_item = QTreeWidgetItem(self.tree, [label])
            # Store the relative path from output_dir/out
            rel = json_path.relative_to(fm.output_dir / "out")
            file_item.setData(0, 200, str(rel))  # relative path for load_recipe
            file_item.setData(0, 201, str(json_path))  # full path

        self.tree.expandAll()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_double_click(self, item: QTreeWidgetItem, _column: int):
        if self._mode == "source":
            self._on_source_double_click(item)
        else:
            self._on_output_double_click(item)

    def _on_source_double_click(self, item: QTreeWidgetItem):
        """Handle double-click in source mode."""
        rel_path = item.data(0, 101)
        if rel_path is None:
            return  # clicked a category node

        # Load markdown content into preview
        if self._fm is not None:
            try:
                content = self._fm.load_markdown(rel_path)
                self._render_markdown(content)
            except Exception:
                self.preview.setHtml(f"<p>[无法加载文件: {rel_path}]</p>")

        # Check if a corresponding JSON already exists in output
        if self._fm is not None:
            file_stem = Path(rel_path).stem
            json_rel = f"{file_stem}.json"
            json_full = self._fm.output_dir / "out" / json_rel
            if json_full.exists():
                # Emit output signal so the form loads the existing JSON
                self.output_file_selected.emit(json_rel)
                return

        self.file_selected.emit(rel_path)

    def _on_output_double_click(self, item: QTreeWidgetItem):
        """Handle double-click in output mode."""
        rel_path = item.data(0, 200)
        if rel_path is None:
            return  # clicked a placeholder node

        # Load JSON content preview
        if self._fm is not None:
            try:
                full_path = self._fm.output_dir / "out" / rel_path
                content = full_path.read_text(encoding="utf-8")
                data = json.loads(content)
                # Pretty-print the JSON
                self.preview.setPlainText(
                    json.dumps(data, ensure_ascii=False, indent=2)
                )
            except Exception as e:
                self.preview.setPlainText(f"[无法加载 JSON: {e}]")

        self.output_file_selected.emit(rel_path)
