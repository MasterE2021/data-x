import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
from PySide6 import QtCore
from src.manager.manager_qss import QSSManager
from space_state import StateSpace
from space_action import ActionSpace


class HomePage(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(900, 600)  # 初始化窗口大小

        # 1. 初始化 UI 组件
        self._init_ui()

        # 2. 初始化 QSS 样式
        self._init_style()

    def _init_ui(self):
        """分离 UI 构建逻辑，保持代码结构清晰"""
        core_space = QWidget()
        core_space.setObjectName("CentralWidget")
        core_space.setAttribute(QtCore.Qt.WA_StyledBackground, True)  # 允许原生 QWidget 响应 QSS 的背景色绘制
        self.setCentralWidget(core_space)

        layout = QVBoxLayout(core_space)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(ActionSpace(), 1)  # 通过拉伸因子使其填充可用空间, 1为完全拉伸, 0为完全不拉伸
        layout.addWidget(StateSpace(), 0)

    def _init_style(self):
        """配置并应用 QSS 样式"""
        self.qss_manager = QSSManager([
            "../style/space.qss",
            "../style/button.qss",
        ])
        self.qss_manager.styleChanged.connect(self.setStyleSheet)  # 直接连接：Qt的信号可以直接连接到内置槽函数，省去了 apply_style 这个包装函数
        self.setStyleSheet(self.qss_manager.load())  # 首次加载：直接调用 setStyleSheet


if __name__ == "__main__":
    app = QApplication(sys.argv)
    home_page = HomePage()
    home_page.show()
    sys.exit(app.exec())
