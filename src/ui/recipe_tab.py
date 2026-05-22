# src/ui/recipe_tab.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QVBoxLayout

from src.parsers.markdown_parser import MarkdownParser
from src.ui.recipe_form import RecipeForm
from src.ui.source_panel import SourcePanel


class RecipeTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)

        # 左栏 - 数据源（目录树 + Markdown 预览）
        self.source_panel = SourcePanel()

        # 中栏 - 编辑区
        self.recipe_form = RecipeForm()

        # 右栏 - 参考区
        right = QVBoxLayout()
        right.addWidget(QLabel("参考区"))
        right_w = QWidget()
        right_w.setLayout(right)

        layout.addWidget(self.source_panel, 1)
        layout.addWidget(self.recipe_form, 2)
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
        """Load MD -> parse with MarkdownParser -> populate RecipeForm."""
        fm = self.source_panel._fm
        if fm is None:
            return
        try:
            content = fm.load_markdown(rel_path)
            parsed = MarkdownParser.parse(content, source_path=rel_path)
            self.recipe_form.load_recipe(parsed)
        except Exception as e:
            print(f"[RecipeTab] Error loading recipe: {e}")
