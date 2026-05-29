# src/ui/recipe_tab.py
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QSplitter,
    QTabWidget,
    QToolBar,
    QMessageBox,
)

from src.parsers.markdown_parser import MarkdownParser
from src.ui.ingredient_panel import IngredientPanel
from src.ui.recipe_form import RecipeForm
from src.ui.source_panel import SourcePanel
from src.ui.unit_panel import UnitPanel


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

        # --- main horizontal splitter: left / middle / right ---
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左栏 - 数据源（目录树 + Markdown 预览）
        self.source_panel = SourcePanel()

        # 中栏 - 编辑区
        self.recipe_form = RecipeForm()

        # 右栏 - 食材库 + 单位库（标签页）
        self.ingredient_panel = IngredientPanel()
        self.unit_panel = UnitPanel()

        self.right_tabs = QTabWidget()
        self.right_tabs.addTab(self.ingredient_panel, "食材库")
        self.right_tabs.addTab(self.unit_panel, "单位库")

        self._main_splitter.addWidget(self.source_panel)
        self._main_splitter.addWidget(self.recipe_form)
        self._main_splitter.addWidget(self.right_tabs)
        self._main_splitter.setStretchFactor(0, 1)
        self._main_splitter.setStretchFactor(1, 4)
        self._main_splitter.setStretchFactor(2, 1)

        outer_layout.addWidget(self._main_splitter)

        # Internal state
        self._im = None  # IngredientManager
        self._um = None  # UnitManager
        self._current_source_path: str | None = None

        # Connect signals
        self.source_panel.file_selected.connect(self._on_file_selected)
        self.source_panel.output_file_selected.connect(self._on_output_file_selected)
        self.recipe_form.save_requested.connect(self._on_save)
        self.recipe_form.dirty_changed.connect(self._on_dirty_changed)
        self.ingredient_panel.ingredient_changed.connect(self._on_ingredients_changed)
        self.ingredient_panel.ingredient_renamed.connect(self._on_ingredient_batch_rename)
        self.ingredient_panel.navigate_to_recipe.connect(self._on_output_file_selected)
        self.unit_panel.unit_changed.connect(self._on_unit_batch_rename)
        self.unit_panel.units_updated.connect(self._on_units_updated)
        self.unit_panel.navigate_to_recipe.connect(self._on_output_file_selected)

        # Parsed results cache: {relative_path: parsed_dict}
        self._parsed_results: dict = {}

        # Ctrl+S shortcut
        self._save_shortcut = QShortcut(QKeySequence.Save, self)
        self._save_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._save_shortcut.activated.connect(self._on_save_shortcut)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        if not hasattr(self, '_sizes_done'):
            QTimer.singleShot(100, self._apply_sizes)

    def _apply_sizes(self):
        w = self._main_splitter.width()
        if w > 0:
            self._main_splitter.setSizes([w // 6, 4 * w // 6, w // 6])
        self._sizes_done = True

    def set_file_manager(self, fm):
        """Propagate the FileManager to sub-panels."""
        self.source_panel.set_file_manager(fm)
        self.ingredient_panel.set_file_manager(fm)
        self.unit_panel.set_file_manager(fm)

    def set_ingredient_manager(self, mgr):
        """Propagate the IngredientManager to the ingredient panel and recipe form."""
        self._im = mgr
        self.ingredient_panel.set_ingredient_manager(mgr)
        self.recipe_form.set_ingredient_manager(mgr)

    def set_unit_manager(self, mgr):
        """Propagate the UnitManager to the unit panel and recipe form."""
        self._um = mgr
        self.unit_panel.set_unit_manager(mgr)
        self.recipe_form.set_unit_manager(mgr)

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
        fm = self.source_panel._fm
        if fm is None:
            return

        # Render markdown preview after confirmation
        try:
            content = fm.load_markdown(rel_path)
            self.source_panel.render_markdown(content)
        except Exception:
            self.source_panel.preview.setHtml(f"<p>[无法加载文件: {rel_path}]</p>")

        self.recipe_form.set_file_source(rel_path, fm)

        # Use cached result if available from batch import
        if rel_path in self._parsed_results:
            self.recipe_form.load_recipe(self._parsed_results[rel_path])
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

            # Render JSON preview after confirmation
            try:
                full_path = fm.output_dir / "out" / rel_path
                content = full_path.read_text(encoding="utf-8")
                import json
                json_data = json.loads(content)
                self.source_panel.preview.setPlainText(
                    json.dumps(json_data, ensure_ascii=False, indent=2)
                )
            except Exception as e:
                self.source_panel.preview.setPlainText(f"[无法加载 JSON: {e}]")

            # Try to load the corresponding source MD for preview
            source_file = data.get("source_file", "")

            # Try multiple strategies to find the source MD
            md_loaded = False

            # Strategy 1: source_file is a valid relative path
            if source_file:
                try:
                    md_content = fm.load_markdown(source_file)
                    self._current_source_path = source_file
                    self.source_panel.render_markdown(md_content)
                    md_loaded = True
                except Exception:
                    pass

            # Strategy 2: source_file contains the filename, extract it
            if not md_loaded and source_file:
                filename = Path(source_file).name
                for src in fm.list_source_files():
                    if src.name == filename:
                        try:
                            src_rel = str(src.relative_to(fm.source_dir))
                            self._current_source_path = src_rel
                            md_content = fm.load_markdown(src_rel)
                            self.source_panel.render_markdown(md_content)
                            md_loaded = True
                        except Exception:
                            pass
                        break

            # Strategy 3: match JSON stem to source file stem
            if not md_loaded:
                json_stem = Path(rel_path).stem
                for src in fm.list_source_files():
                    if src.stem == json_stem:
                        try:
                            src_rel = str(src.relative_to(fm.source_dir))
                            self._current_source_path = src_rel
                            md_content = fm.load_markdown(src_rel)
                            self.source_panel.render_markdown(md_content)
                            md_loaded = True
                        except Exception:
                            pass
                        break

            # Pass source path to form for quick import
            if self._current_source_path:
                self.recipe_form.set_file_source(self._current_source_path, fm)
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

        # Determine output relative path — always flat under out/
        source_path = data.get("source_file") or self._current_source_path or ""
        if source_path:
            output_rel = Path(source_path).stem + ".json"
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

        # 4. Refresh ingredient and unit panels (updates usage counts)
        self.ingredient_panel.refresh_list()
        self.unit_panel.refresh_list()

        # 5. Show status message
        status_bar = self.window().statusBar() if self.window() else None
        if status_bar is not None:
            status_bar.showMessage(f"已保存: {recipe_name}", 3000)

        # 6. Mark form as clean
        self.recipe_form.set_clean()

        print(f"[RecipeTab] 已保存: {recipe_name}")

    def _on_save_shortcut(self):
        """Handle Ctrl+S: trigger save if the form has content."""
        if self.recipe_form.is_dirty():
            self.recipe_form._on_save_clicked()
        else:
            status_bar = self.window().statusBar() if self.window() else None
            if status_bar is not None:
                status_bar.showMessage("无更改需要保存", 2000)

    def _on_dirty_changed(self, dirty: bool):
        """Update UI indicators when dirty state changes."""
        # Update save button text
        self.recipe_form.save_btn.setText("保存 *" if dirty else "保存")

        # Update tab title
        tab_widget = self.parent()
        if isinstance(tab_widget, QTabWidget):
            index = tab_widget.indexOf(self)
            if index >= 0:
                base = "菜谱编辑"
                tab_widget.setTabText(index, f"{base} *" if dirty else base)

    def _on_ingredients_changed(self):
        """Sync ingredient changes: update completer and persist to ingredients.json."""
        if self._im is not None:
            self.recipe_form.set_ingredient_manager(self._im)

        fm = self.source_panel._fm
        if fm is not None and self._im is not None:
            try:
                ingredients_data = {}
                for ing in self._im.get_all():
                    ingredients_data[ing.key] = ing.to_dict()
                fm.save_ingredients(ingredients_data)
            except Exception as e:
                print(f"[RecipeTab] Warning: could not save ingredients.json: {e}")

    def _on_ingredient_batch_rename(self, old_name: str, new_name: str):
        """Apply ingredient rename to current recipe form and all recipe JSON files."""
        self.recipe_form.batch_rename_ingredient(old_name, new_name)
        # Update all recipe JSON files on disk
        fm = self.source_panel._fm
        if fm is not None and self._im is not None:
            recipe_files = [fm.output_dir / "out" / p.name for p in fm.list_output_recipes()]
            modified = self._im.update_all_recipes(recipe_files, {old_name: new_name})
            if modified:
                fm.invalidate_usage_cache()
                print(f"[RecipeTab] Renamed ingredient '{old_name}' -> '{new_name}' in {modified} recipe file(s)")

    def _on_unit_batch_rename(self, old_name: str, new_name: str):
        """Apply unit rename to current recipe form and all recipe JSON files.

        Also normalize all aliases to primary names across all files.
        """
        self.recipe_form.batch_rename_unit(old_name, new_name)
        # Update all recipe JSON files on disk
        fm = self.source_panel._fm
        if fm is not None and self._um is not None:
            recipe_files = [fm.output_dir / "out" / p.name for p in fm.list_output_recipes()]
            self._um.update_all_recipes(recipe_files, {old_name: new_name})
            # Normalize all aliases to primary names (skip if alias is a primary name itself)
            primary_names = {u.name for u in self._um.get_all()}
            all_normalizations: dict[str, str] = {}
            for unit in self._um.get_all():
                for alias in unit.aliases:
                    if alias != unit.name and alias not in primary_names:
                        all_normalizations[alias] = unit.name
            if all_normalizations:
                modified = self._um.update_all_recipes(recipe_files, all_normalizations)
                if modified:
                    print(f"[RecipeTab] Normalized {modified} recipe file(s): aliases → primary names")
            # Also apply to current form
            for old_alias, new_alias in all_normalizations.items():
                self.recipe_form.batch_rename_unit(old_alias, new_alias)

    def _on_units_updated(self):
        """Sync unit changes: refresh combo boxes in recipe form, normalize aliases, persist."""
        if self._um is not None:
            self.recipe_form.set_unit_manager(self._um)
        # Normalize aliases to primary names across all recipe files.
        # Only normalize if the alias is NOT itself a primary name of another unit
        # (this allows split aliases to remain as standalone units).
        fm = self.source_panel._fm
        if fm is not None and self._um is not None:
            recipe_files = [fm.output_dir / "out" / p.name for p in fm.list_output_recipes()]
            primary_names = {u.name for u in self._um.get_all()}
            all_normalizations: dict[str, str] = {}
            for unit in self._um.get_all():
                for alias in unit.aliases:
                    if alias != unit.name and alias not in primary_names:
                        all_normalizations[alias] = unit.name
            if all_normalizations:
                modified = self._um.update_all_recipes(recipe_files, all_normalizations)
                if modified:
                    print(f"[RecipeTab] Normalized {modified} recipe file(s): aliases → primary names")
            # Also apply to current form
            for old_name, new_name in all_normalizations.items():
                self.recipe_form.batch_rename_unit(old_name, new_name)
        # Persist units
        if fm is not None and self._um is not None:
            try:
                import json
                from pathlib import Path
                units_path = fm.output_dir / "out" / "units.json"
                units_path.parent.mkdir(parents=True, exist_ok=True)
                units_path.write_text(
                    json.dumps(self._um.to_list(), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception as e:
                print(f"[RecipeTab] Warning: could not save units.json: {e}")

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
