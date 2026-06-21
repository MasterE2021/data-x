import sys
from PySide6.QtWidgets import QApplication
from src.gui.ui_home import HomePage
import os

if __name__ == "__main__":
    # 获取项目根路径
    path = os.path.dirname(os.path.abspath(__file__))
    root_dir = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(path)

    # 项目启动
    app = QApplication(sys.argv)
    home_page = HomePage(root_dir)
    home_page.show()
    sys.exit(app.exec())
