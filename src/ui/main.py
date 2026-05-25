# src/ui/main.py
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenuBar,
    QPushButton,
    QTabWidget,
)
from PySide6.QtCore import Qt, QThread, Signal

from src.managers.file_manager import FileManager
from src.managers.ingredient_manager import IngredientManager
from src.managers.nutrition_matcher import NutritionMatcher
from src.managers.unit_manager import UnitManager
from src.managers.git_utils import GitRepo
from src.ui.settings_dialog import SettingsDialog

CATEGORY_EN_TO_ZH = {
    "vegetables": "蔬菜", "meat": "肉类", "seafood": "水产",
    "eggs": "禽蛋", "dairy": "豆制品", "grains": "主食/谷物",
    "seasoning": "调料", "beverages": "饮品", "oil": "干货",
    "fruits": "水果", "nuts": "坚果", "others": "其他",
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HowToCook JSON Organizer")
        self.resize(1400, 900)

        # Managers (initialised when valid config is available)
        self._fm: FileManager | None = None
        self._im: IngredientManager | None = None
        self._nm: NutritionMatcher | None = None

        # Tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        from src.ui.recipe_tab import RecipeTab
        from src.ui.nutrition_tab import NutritionTab

        self.recipe_tab = RecipeTab()
        self.nutrition_tab = NutritionTab()

        self.tabs.addTab(self.recipe_tab, "菜谱编辑")
        self.tabs.addTab(self.nutrition_tab, "食材营养管理")

        # Menu bar
        menu_bar: QMenuBar = self.menuBar()
        settings_menu = menu_bar.addMenu("工具")
        settings_action = settings_menu.addAction("设置...")
        settings_action.triggered.connect(self._open_settings)

        self._sync_action = settings_menu.addAction("仓库同步")
        self._sync_action.triggered.connect(self._on_git_sync)

        # Status bar with sync button
        self._status_sync_btn = QPushButton("⟳ 同步")
        self._status_sync_btn.clicked.connect(self._on_git_sync)
        self._status_sync_btn.setToolTip("仓库同步：拉取、提交、推送")
        self.statusBar().addPermanentWidget(self._status_sync_btn)

        self.statusBar().showMessage("就绪")

        # Attempt to load config on startup
        self._try_apply_config(auto_show=True)

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    def _try_apply_config(self, auto_show: bool = False) -> bool:
        """Load config from disk and initialise managers.

        If *auto_show* is True and config is missing/invalid, automatically
        open the SettingsDialog.
        """
        config = SettingsDialog.load_config()
        ok, _ = SettingsDialog.validate_paths(config)
        if not ok:
            if auto_show:
                self._open_settings()
            return False
        self._apply_config(config)
        return True

    def _apply_config(self, config: dict) -> None:
        """(Re-)initialise managers from *config* and propagate to tabs."""
        source_dir = Path(config["source_dir"])
        output_dir = Path(config["output_dir"])

        # File manager
        self._fm = FileManager(source_dir=source_dir, output_dir=output_dir)
        self.recipe_tab.set_file_manager(self._fm)

        # Ingredient manager
        self._im = IngredientManager()
        # Load persisted ingredients if available
        ingredients_data = self._fm.load_ingredients()
        if ingredients_data:
            items = ingredients_data.values() if isinstance(ingredients_data, dict) else ingredients_data
            for item in items:
                # Support both "name" and "ingredient_name" field names
                name = item.get("name") or item.get("ingredient_name", "")
                aliases = item.get("aliases", [])
                category_raw = item.get("category", "其他")
                # Translate English category to Chinese
                category = CATEGORY_EN_TO_ZH.get(category_raw, category_raw)
                if name:
                    self._im.add(name=name, aliases=aliases, category=category)
        self.recipe_tab.set_ingredient_manager(self._im)
        self.nutrition_tab.set_ingredient_manager(self._im)

        # Unit manager — persisted data takes priority over defaults
        self._um = UnitManager()
        import json as _json

        units_path = output_dir / "out" / "units.json"
        loaded_from_file = False
        if units_path.exists():
            try:
                raw_units = _json.loads(units_path.read_text(encoding="utf-8"))
                if isinstance(raw_units, list) and raw_units:
                    self._um.load_from_list(raw_units)
                    loaded_from_file = True
            except Exception:
                pass

        if not loaded_from_file:
            self._um._load_defaults()

        # Discover new units from existing recipe JSON files
        recipe_files = self._fm.list_output_recipes()
        discovered_units = self._um.discover_from_recipes(recipe_files)
        if discovered_units:
            new_count = self._um.add_discovered_units(discovered_units)
            if new_count:
                print(f"[MainWindow] Discovered {new_count} new unit(s) from recipes: {discovered_units}")
        self.recipe_tab.set_unit_manager(self._um)

        # Nutrition matcher (loaded from nutritions.json if present)
        nutritions_path = output_dir / "out" / "nutritions.json"
        usda_data: list[dict] = []
        if nutritions_path.exists():
            import json
            try:
                raw = json.loads(nutritions_path.read_text(encoding="utf-8"))
                usda_data = self._convert_nutritions(raw)
            except Exception:
                usda_data = []

        self._nm = NutritionMatcher(usda_data)
        self.nutrition_tab.set_nutrition_matcher(self._nm)

        self.statusBar().showMessage(
            f"已加载 — 源: {source_dir}  输出: {output_dir}"
        )

    @staticmethod
    def _convert_nutritions(raw: list) -> list[dict]:
        """将实际 nutritions.json 格式转为 NutritionMatcher 期望的格式。

        实际格式: [{"usda_id": 123, "ingredient_name": "番茄", "usda_name": "Tomato",
                    "nutrients": {"energy": {"value": 18, "unit": "kcal"}, ...}}]
        期望格式: [{"fdc_id": 123, "description": "Tomato", "description_zh": "番茄",
                    "nutrients": [{"name": "energy", "name_zh": "energy", "amount": 18, "unit": "kcal"}]}]
        """
        result = []
        for item in raw:
            nutrients = []
            raw_nutrients = item.get("nutrients", {})
            if isinstance(raw_nutrients, dict):
                for key, val in raw_nutrients.items():
                    if isinstance(val, dict) and "value" in val:
                        nutrients.append({
                            "name": key,
                            "name_zh": key,
                            "amount": val.get("value", 0),
                            "unit": val.get("unit", ""),
                        })
            result.append({
                "fdc_id": item.get("usda_id", 0),
                "description": item.get("usda_name", ""),
                "description_zh": item.get("ingredient_name", ""),
                "nutrients": nutrients,
            })
        return result

    # ------------------------------------------------------------------
    # Git sync
    # ------------------------------------------------------------------

    def _run_git_sync(self) -> None:
        """Run startup sync dialog if output_dir is a valid git repo."""
        try:
            if self._fm is None:
                return
            output_dir = self._fm.output_dir
            repo = GitRepo(output_dir)
            if not repo.is_git_available():
                return
            if not repo.is_valid_repo():
                return
            if not repo.has_remote():
                return

            from src.ui.git_sync_dialog import GitSyncDialog
            dlg = GitSyncDialog(output_dir, parent=self)
            dlg.exec()
        except Exception as e:
            # Ensure sync errors never prevent the main window from showing
            import logging
            logging.warning(f"Git sync failed: {e}")
            pass

    def _on_git_sync(self) -> None:
        """Menu/status-bar sync: pull → add → commit → push directly."""
        if self._fm is None:
            self.statusBar().showMessage("请先设置仓库路径", 3000)
            return
        output_dir = self._fm.output_dir
        repo = GitRepo(output_dir)

        if not repo.is_git_available():
            self.statusBar().showMessage("未找到 git", 3000)
            return
        if not repo.is_valid_repo():
            self.statusBar().showMessage("输出目录不是 git 仓库", 3000)
            return
        if not repo.has_remote():
            self.statusBar().showMessage("仓库没有配置远程", 3000)
            return

        self._sync_action.setEnabled(False)
        self._status_sync_btn.setEnabled(False)
        self.statusBar().showMessage("正在同步...")

        self._sync_worker = _ManualSyncWorker(repo)
        self._sync_worker.progress.connect(self.statusBar().showMessage)
        self._sync_worker.done.connect(self._on_sync_done)
        self._sync_worker.error_occurred.connect(self._on_sync_error)
        self._sync_worker.conflict.connect(self._on_sync_conflict)
        self._sync_worker.start()

    def _on_sync_done(self, message: str) -> None:
        self._sync_action.setEnabled(True)
        self._status_sync_btn.setEnabled(True)
        self.statusBar().showMessage(message, 5000)

    def _on_sync_error(self, message: str) -> None:
        self._sync_action.setEnabled(True)
        self._status_sync_btn.setEnabled(True)
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "同步失败", message)

    def _on_sync_conflict(self, conflicts: list[str]) -> None:
        from src.ui.git_sync_dialog import GitSyncDialog
        repo = GitRepo(self._fm.output_dir)
        continue_ok = GitSyncDialog.show_conflict_dialog(repo, conflicts, parent=self)
        if continue_ok:
            # User resolved conflicts externally, try to finish
            self._finish_sync_after_conflict(repo)
        else:
            self._sync_action.setEnabled(True)
            self._status_sync_btn.setEnabled(True)
            self.statusBar().showMessage("已放弃合并")

    def _finish_sync_after_conflict(self, repo: GitRepo) -> None:
        """After user resolves conflicts, add → commit → push."""
        self.statusBar().showMessage("正在提交并推送...")
        repo.add_all()

        changes = repo.check_local_changes()
        msg = GitRepo.format_commit_message(changes.modified_files, changes.untracked_files)
        ok, result = repo.commit(msg)
        if not ok:
            self._sync_action.setEnabled(True)
            self._status_sync_btn.setEnabled(True)
            self.statusBar().showMessage(result, 5000)
            return

        ok, result = repo.push()
        self._sync_action.setEnabled(True)
        self._status_sync_btn.setEnabled(True)
        self.statusBar().showMessage(result if ok else result, 5000)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self)
        dlg.set_config(SettingsDialog.load_config())
        if dlg.exec():
            config = dlg.get_config()
            self._apply_config(config)


class _ManualSyncWorker(QThread):
    """Background worker for menu-mode sync (direct pull→commit→push)."""
    progress = Signal(str)
    done = Signal(str)
    error_occurred = Signal(str)
    conflict = Signal(list)

    def __init__(self, repo: GitRepo):
        super().__init__()
        self.repo = repo

    def run(self) -> None:
        try:
            # 1. Pull (with stash if needed)
            self.progress.emit("正在拉取远程更新...")
            success, msg, _had_stash, conflicts = self.repo.pull_with_stash()
            self.progress.emit(msg)

            if not success:
                if conflicts:
                    self.conflict.emit(conflicts)
                else:
                    self.error_occurred.emit(msg)
                return

            # 2. Check for local changes
            self.progress.emit("正在检查本地更改...")
            changes = self.repo.check_local_changes()

            if changes.has_changes:
                self.progress.emit("正在暂存更改...")
                self.repo.add_all()

                commit_msg = GitRepo.format_commit_message(
                    changes.modified_files, changes.untracked_files
                )
                self.progress.emit(f"正在提交: {commit_msg}")
                ok, result = self.repo.commit(commit_msg)
                if not ok:
                    self.progress.emit(f"提交: {result}")
                else:
                    self.progress.emit("正在推送到远程...")
                    ok, push_msg = self.repo.push(
                        progress_callback=lambda line: self.progress.emit(line),
                    )
                    self.progress.emit(push_msg)
            else:
                self.progress.emit("无本地更改，无需提交")

            self.done.emit("同步完成")
        except Exception as e:
            self.error_occurred.emit(f"同步失败: {e}")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.move(
        (screen := app.primaryScreen().availableGeometry()).center().x() - window.width() // 2,
        screen.center().y() - window.height() // 2,
    )
    window._run_git_sync()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
