# src/ui/recipe_tab.py
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QToolBar,
    QMessageBox,
)

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

        # Internal state
        self._im = None  # IngredientManager
        self._current_source_path: str | None = None

        # Connect signals
        self.source_panel.file_selected.connect(self._on_file_selected)
        self.source_panel.output_file_selected.connect(self._on_output_file_selected)
        self.recipe_form.save_requested.connect(self._on_save)

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
        self._im = mgr
        self.ingredient_panel.set_ingredient_manager(mgr)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _confirm_discard_unsaved(self) -> bool:
        """If the form has unsaved changes, ask the user to confirm.

        Returns True if it is OK to proceed (discard / no unsaved changes).
        """
        if not self.recipe_form.is_dirty():
            return True
        reply = QMessageBox.question(
            self,
            "未保存的更改",
            "当前菜谱未保存，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _on_file_selected(self, rel_path: str):
        """Load MD -> parse with MarkdownParser -> populate RecipeForm."""
        if not self._confirm_discard_unsaved():
            return

        self._current_source_path = rel_path

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
        if not self._confirm_discard_unsaved():
            return

        fm = self.source_panel._fm
        if fm is None:
            return
        try:
            data = fm.load_recipe(rel_path)
            self.recipe_form.load_recipe(data)

            # Try to load the corresponding source MD for preview
            source_file = data.get("source_file", "")
            if source_file:
                self._current_source_path = source_file
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
                            self._current_source_path = src_rel
                            md_content = fm.load_markdown(src_rel)
                            self.source_panel.preview.setPlainText(md_content)
                        except Exception:
                            pass
                        break
        except Exception as e:
            print(f"[RecipeTab] Error loading output recipe: {e}")

    def _on_save(self, data: dict):
        """Handle save_requested from RecipeForm.

        1. Write recipe JSON via FileManager
        2. Sync new ingredient names to IngredientManager + ingredients.json
        3. Refresh the source panel tree (update check marks)
        4. Show a status bar message
        5. Mark the form as clean
        """
        fm = self.source_panel._fm
        if fm is None:
            print("[RecipeTab] Cannot save: no FileManager")
            return

        recipe_name = data.get("name", "未命名")

        # Determine output relative path
        source_path = data.get("source_file") or self._current_source_path or ""
        if source_path:
            # Replace .md extension with .json, keep directory structure
            output_rel = source_path.rsplit(".", 1)[0] + ".json"
        else:
            # Fallback: put in root with recipe name
            output_rel = f"{recipe_name}.json"

        # Update source_file in data
        data["source_file"] = source_path

        # 1. Save recipe JSON
        try:
            fm.save_recipe(output_rel, data)
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"无法保存菜谱: {e}")
            return

        # 2. Sync ingredients
        if self._im is not None:
            new_names = []
            for ing in data.get("ingredients", []):
                ing_name = ing.get("ingredient_name", "").strip()
                if not ing_name:
                    continue
                existing = self._im.get_by_name(ing_name)
                if existing is None:
                    self._im.add(name=ing_name)
                    new_names.append(ing_name)

            # Save ingredients.json
            if new_names:
                try:
                    ingredients_data = {}
                    for ing in self._im.get_all():
                        ingredients_data[ing.key] = ing.to_dict()
                    fm.save_ingredients(ingredients_data)
                except Exception as e:
                    print(f"[RecipeTab] Warning: could not save ingredients.json: {e}")

        # 3. Refresh source panel tree (updates check marks)
        self.source_panel.refresh_tree()

        # 4. Show status message
        status_bar = self.window().statusBar() if self.window() else None
        if status_bar is not None:
            status_bar.showMessage(f"已保存: {recipe_name}", 3000)

        # 5. Mark form as clean
        self.recipe_form.set_clean()

        print(f"[RecipeTab] 已保存: {recipe_name}")

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
