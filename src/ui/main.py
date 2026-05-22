# src/ui/main.py
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenuBar,
    QTabWidget,
)
from PySide6.QtCore import Qt

from src.managers.file_manager import FileManager
from src.managers.ingredient_manager import IngredientManager
from src.managers.nutrition_matcher import NutritionMatcher
from src.managers.unit_manager import UnitManager
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

        # Menu bar — Settings action
        menu_bar: QMenuBar = self.menuBar()
        settings_menu = menu_bar.addMenu("工具")
        settings_action = settings_menu.addAction("设置...")
        settings_action.triggered.connect(self._open_settings)

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

        # Unit manager
        self._um = UnitManager()
        # Load persisted custom units if available
        units_path = output_dir / "out" / "units.json"
        if units_path.exists():
            import json as _json
            try:
                raw_units = _json.loads(units_path.read_text(encoding="utf-8"))
                if isinstance(raw_units, list):
                    self._um.load_from_list(raw_units)
            except Exception:
                pass
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
    # Slots
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self)
        dlg.set_config(SettingsDialog.load_config())
        if dlg.exec():
            config = dlg.get_config()
            self._apply_config(config)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.move(
        (screen := app.primaryScreen().availableGeometry()).center().x() - window.width() // 2,
        screen.center().y() - window.height() // 2,
    )
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
