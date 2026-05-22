# src/ui/nutrition_tab.py
from PySide6.QtWidgets import QHBoxLayout, QWidget

from src.managers.ingredient_manager import IngredientManager
from src.managers.nutrition_matcher import NutritionMatcher
from src.ui.nutrition_ingredient_list import NutritionIngredientList
from src.ui.nutrition_panel import NutritionPanel


class NutritionTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)

        # 左栏 - 食材列表
        self._ingredient_list = NutritionIngredientList()
        layout.addWidget(self._ingredient_list, 1)

        # 中栏 + 右栏 - 匹配操作与营养详情
        self._panel = NutritionPanel()
        layout.addWidget(self._panel, 2)

        # 信号连接: 左栏选中食材 -> 中栏加载详情
        self._ingredient_list.ingredient_selected.connect(
            self._panel.set_ingredient
        )

    def set_ingredient_manager(self, mgr: IngredientManager) -> None:
        self._ingredient_list.set_ingredient_manager(mgr)
        self._panel.set_ingredient_manager(mgr)

    def set_nutrition_matcher(self, matcher: NutritionMatcher) -> None:
        self._panel.set_nutrition_matcher(matcher)
