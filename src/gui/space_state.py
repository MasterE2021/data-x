from PySide6.QtWidgets import QWidget
from PySide6 import QtCore


class StateSpace(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("StateSpace")
        self.setFixedHeight(30)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)  # 允许自定义 QWidget 子类应用 QSS 背景样式
