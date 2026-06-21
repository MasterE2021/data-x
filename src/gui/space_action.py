from PySide6.QtWidgets import QWidget, QHBoxLayout
from PySide6 import QtCore


class ActionSpace(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("ActionSpace")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)  # 允许自定义 QWidget 子类应用 QSS 背景样式

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolBar = QWidget()
        toolBar.setObjectName("ToolBar")
        toolBar.setFixedWidth(30)
        toolBar.setAttribute(QtCore.Qt.WA_StyledBackground, True)

        work_space = QWidget()
        work_space.setObjectName("WorkSpace")
        work_space.setAttribute(QtCore.Qt.WA_StyledBackground, True)

        layout.addWidget(toolBar, 0)
        layout.addWidget(work_space, 1)
