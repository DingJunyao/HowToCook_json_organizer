# src/ui/nutrition_tab.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QVBoxLayout

class NutritionTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)

        # 左栏 - 食材列表
        left = QVBoxLayout()
        left.addWidget(QLabel("食材列表"))
        left_w = QWidget()
        left_w.setLayout(left)

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

        layout.addWidget(left_w, 1)
        layout.addWidget(center_w, 1)
        layout.addWidget(right_w, 1)
