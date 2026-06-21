from PySide6.QtWidgets import QWidget
from PySide6 import QtCore


class WorkSpace(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("WorkSpace")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
