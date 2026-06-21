from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton
from PySide6 import QtCore
from src.gui.space_work import WorkSpace
from src.manager.manager_db import SQLiteManager


class ActionSpace(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("ActionSpace")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)  # 允许自定义 QWidget 子类应用 QSS 背景样式

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(ToolBar(), 0)
        layout.addWidget(WorkSpace(), 1)


class ToolBar(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("ToolBar")
        self.setFixedWidth(40)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 按钮支撑组件
        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().Policy.Expanding, spacer.sizePolicy().Policy.Preferred)

        layout.addWidget(FileButton())
        layout.addWidget(ExecButton())
        layout.addWidget(ImportButton())
        layout.addWidget(ExportButton())
        layout.addWidget(spacer)


class FileButton(QPushButton):
    def __init__(self):
        super().__init__()
        self.setText("文件")
        self.setObjectName("FileButton")


class ExecButton(QPushButton):
    def __init__(self):
        super().__init__()
        self.setText("执行")
        self.setObjectName("ExecButton")


class ImportButton(QPushButton):
    def __init__(self):
        super().__init__()
        self.setText("导入")
        self.setObjectName("ImportButton")
        self.clicked.connect(SQLiteManager.import_requested)


class ExportButton(QPushButton):
    def __init__(self):
        super().__init__()
        self.setText("导出")
        self.setObjectName("ExportButton")
