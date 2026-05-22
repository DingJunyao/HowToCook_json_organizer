# src/ui/recipe_tab.py
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QToolBar

from src.parsers.markdown_parser import MarkdownParser
from src.ui.ingredient_panel import IngredientPanel
from src.ui.recipe_form import RecipeForm
from src.ui.source_panel import SourcePanel


class RecipeTab(QWidget):
    def __init__(self):
        super().__init__()
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # --- toolbar ---
        self._toolbar = QToolBar()
        self._toolbar.setMovable(False)
        self._batch_btn = QPushButton("批量导入")
        self._batch_btn.setToolTip("解析所有源 MD 文件并更新状态")
        self._batch_btn.clicked.connect(self._on_batch_import)
        self._toolbar.addWidget(self._batch_btn)
        outer_layout.addWidget(self._toolbar)

        # --- main horizontal layout ---
        main_widget = QWidget()
        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # 左栏 - 数据源（目录树 + Markdown 预览）
        self.source_panel = SourcePanel()

        # 中栏 - 编辑区
        self.recipe_form = RecipeForm()

        # 右栏 - 食材库参考
        self.ingredient_panel = IngredientPanel()

        layout.addWidget(self.source_panel, 1)
        layout.addWidget(self.recipe_form, 2)
        layout.addWidget(self.ingredient_panel, 1)

        outer_layout.addWidget(main_widget)

        # Connect signals
        self.source_panel.file_selected.connect(self._on_file_selected)
        self.source_panel.output_file_selected.connect(self._on_output_file_selected)

        # Parsed results cache: {relative_path: parsed_dict}
        self._parsed_results: dict = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_file_manager(self, fm):
        """Propagate the FileManager to the source panel."""
        self.source_panel.set_file_manager(fm)

    def set_ingredient_manager(self, mgr):
        """Propagate the IngredientManager to the ingredient panel."""
        self.ingredient_panel.set_ingredient_manager(mgr)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_file_selected(self, rel_path: str):
        """Load MD -> parse with MarkdownParser -> populate RecipeForm."""
        # Use cached result if available from batch import
        if rel_path in self._parsed_results:
            self.recipe_form.load_recipe(self._parsed_results[rel_path])
            return

        fm = self.source_panel._fm
        if fm is None:
            return
        try:
            content = fm.load_markdown(rel_path)
            parsed = MarkdownParser.parse(content, source_path=rel_path)
            self.recipe_form.load_recipe(parsed)
        except Exception as e:
            print(f"[RecipeTab] Error loading recipe: {e}")

    def _on_output_file_selected(self, rel_path: str):
        """Load an existing JSON output file into the form for editing.

        1. Loads the JSON via FileManager.load_recipe()
        2. Populates the form with the data
        3. Tries to find and display the source MD in the preview area
        """
        fm = self.source_panel._fm
        if fm is None:
            return
        try:
            data = fm.load_recipe(rel_path)
            self.recipe_form.load_recipe(data)

            # Try to load the corresponding source MD for preview
            source_file = data.get("source_file", "")
            if source_file:
                try:
                    md_content = fm.load_markdown(source_file)
                    self.source_panel.preview.setPlainText(md_content)
                except Exception:
                    pass  # source MD not available, that's okay
            else:
                # Fallback: try to find by recipe name matching the JSON stem
                json_stem = rel_path.rsplit("/", 1)[-1].replace(".json", "")
                for src in fm.list_source_files():
                    if src.stem == json_stem:
                        try:
                            src_rel = str(src.relative_to(fm.source_dir))
                            md_content = fm.load_markdown(src_rel)
                            self.source_panel.preview.setPlainText(md_content)
                        except Exception:
                            pass
                        break
        except Exception as e:
            print(f"[RecipeTab] Error loading output recipe: {e}")

    def _on_batch_import(self):
        """Parse all source MD files at once and update status icons."""
        fm = self.source_panel._fm
        if fm is None:
            return

        source_files = fm.list_source_files()
        output_stems = {p.stem for p in fm.list_output_recipes()}

        results: dict[str, str] = {}
        self._parsed_results.clear()

        for full_path in source_files:
            rel_path = str(full_path.relative_to(fm.source_dir))
            file_stem = full_path.stem

            # Already has JSON output
            if file_stem in output_stems:
                results[rel_path] = "processed"
                try:
                    content = fm.load_markdown(rel_path)
                    parsed = MarkdownParser.parse(content, source_path=rel_path)
                    self._parsed_results[rel_path] = parsed
                except Exception:
                    pass
                continue

            # Try to parse
            try:
                content = fm.load_markdown(rel_path)
                parsed = MarkdownParser.parse(content, source_path=rel_path)
                self._parsed_results[rel_path] = parsed
                results[rel_path] = "parsed"
            except Exception:
                results[rel_path] = "error"

        self.source_panel.update_parse_status(results)
        print(
            f"[RecipeTab] 批量导入完成: "
            f"{sum(1 for v in results.values() if v == 'processed')} 已处理, "
            f"{sum(1 for v in results.values() if v == 'parsed')} 新解析, "
            f"{sum(1 for v in results.values() if v == 'error')} 错误"
        )
