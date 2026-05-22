# src/ui/recipe_tab.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QVBoxLayout

from src.ui.source_panel import SourcePanel


class RecipeTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)

        # 左栏 - 数据源（目录树 + Markdown 预览）
        self.source_panel = SourcePanel()

        # 中栏 - 编辑区
        center = QVBoxLayout()
        center.addWidget(QLabel("编辑区"))
        center_w = QWidget()
        center_w.setLayout(center)

        # 右栏 - 参考区
        right = QVBoxLayout()
        right.addWidget(QLabel("参考区"))
        right_w = QWidget()
        right_w.setLayout(right)

        layout.addWidget(self.source_panel, 1)
        layout.addWidget(center_w, 1)
        layout.addWidget(right_w, 1)

        # Connect signals
        self.source_panel.file_selected.connect(self._on_file_selected)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_file_manager(self, fm):
        """Propagate the FileManager to the source panel."""
        self.source_panel.set_file_manager(fm)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_file_selected(self, rel_path: str):
        # Placeholder — will be wired to center panel later
        print(f"[RecipeTab] file selected: {rel_path}")
