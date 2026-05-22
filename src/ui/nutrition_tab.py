# src/ui/nutrition_tab.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QVBoxLayout

from src.managers.ingredient_manager import IngredientManager
from src.ui.nutrition_ingredient_list import NutritionIngredientList


class NutritionTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)

        # 左栏 - 食材列表
        self._ingredient_list = NutritionIngredientList()
        layout.addWidget(self._ingredient_list, 1)

        # 中栏 - 匹配操作
        center = QVBoxLayout()
        center.addWidget(QLabel("匹配操作"))
        center_w = QWidget()
        center_w.setLayout(center)

        # 右栏 - 营养详情
        right = QVBoxLayout()
        right.addWidget(QLabel("营养详情"))
        right_w = QWidget()
        right_w.setLayout(right)

        layout.addWidget(center_w, 1)
        layout.addWidget(right_w, 1)

    def set_ingredient_manager(self, mgr: IngredientManager) -> None:
        self._ingredient_list.set_ingredient_manager(mgr)
