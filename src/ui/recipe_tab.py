# src/ui/recipe_tab.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QVBoxLayout

class RecipeTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)

        # 左栏 - 数据源
        left = QVBoxLayout()
        left.addWidget(QLabel("数据源"))
        left_w = QWidget()
        left_w.setLayout(left)

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

        layout.addWidget(left_w, 1)
        layout.addWidget(center_w, 1)
        layout.addWidget(right_w, 1)
