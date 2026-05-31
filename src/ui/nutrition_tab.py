# src/ui/nutrition_tab.py
from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout, QWidget

from src.managers.file_manager import FileManager
from src.managers.ingredient_manager import IngredientManager
from src.managers.nutrition_matcher import NutritionMatcher
from src.ui.merge_dialog import MergeDialog
from src.ui.nutrition_ingredient_list import NutritionIngredientList
from src.ui.nutrition_panel import NutritionPanel


class NutritionTab(QWidget):
    def __init__(self):
        super().__init__()
        self._manager: IngredientManager | None = None
        self._fm: FileManager | None = None
        outer = QHBoxLayout(self)

        # 左栏 - 食材列表 + 工具按钮
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._ingredient_list = NutritionIngredientList()
        left_layout.addWidget(self._ingredient_list, 1)

        # 合并按钮
        self._merge_btn = QPushButton("合并选中食材")
        self._merge_btn.clicked.connect(self._on_merge_clicked)
        left_layout.addWidget(self._merge_btn)

        outer.addWidget(left_widget, 1)

        # 中栏 + 右栏 - 匹配操作与营养详情
        self._panel = NutritionPanel()
        outer.addWidget(self._panel, 2)

        # 信号连接: 左栏选中食材 -> 中栏加载详情
        self._ingredient_list.ingredient_selected.connect(
            self._panel.set_ingredient
        )
        # 信号连接: 匹配/取消匹配 -> 保存并刷新
        self._panel.ingredient_updated.connect(self._on_ingredient_updated)

    def set_ingredient_manager(self, mgr: IngredientManager) -> None:
        self._manager = mgr
        self._ingredient_list.set_ingredient_manager(mgr)
        self._panel.set_ingredient_manager(mgr)

    def set_file_manager(self, fm: FileManager) -> None:
        self._fm = fm

    def set_nutrition_matcher(self, matcher: NutritionMatcher) -> None:
        self._panel.set_nutrition_matcher(matcher)

    def set_on_usda_import(self, callback: callable) -> None:
        self._panel.set_on_usda_import(callback)

    def _on_ingredient_updated(self) -> None:
        """保存食材数据（包含 USDA 匹配信息）并刷新左侧列表。"""
        if self._fm is not None and self._manager is not None:
            try:
                ingredients_data = {}
                for ing in self._manager.get_all():
                    ingredients_data[ing.key] = ing.to_dict()
                self._fm.save_ingredients(ingredients_data)
            except Exception as e:
                print(f"[NutritionTab] Warning: could not save ingredients.json: {e}")
        self._ingredient_list.refresh_list()

    def _on_merge_clicked(self) -> None:
        if self._manager is None:
            return

        selected_keys = self._ingredient_list.get_selected_keys()

        # Determine pre-selected names
        preselect_a: str | None = None
        preselect_b: str | None = None
        if len(selected_keys) >= 2:
            ing_a = self._find_ingredient(selected_keys[0])
            ing_b = self._find_ingredient(selected_keys[1])
            if ing_a:
                preselect_a = ing_a.name
            if ing_b:
                preselect_b = ing_b.name

        dialog = MergeDialog(
            self._manager,
            preselect_a=preselect_a,
            preselect_b=preselect_b,
            parent=self,
        )
        if dialog.exec() == MergeDialog.DialogCode.Accepted:
            keep_name, remove_name = dialog.get_merge_params()
            self._manager.merge(keep_name, remove_name)
            self._refresh_all()

    def _find_ingredient(self, key: str):
        if self._manager is None:
            return None
        for ing in self._manager.get_all():
            if ing.key == key:
                return ing
        return None

    def _refresh_all(self) -> None:
        self._ingredient_list.refresh_list()
        self._panel.ingredient_updated.emit()
