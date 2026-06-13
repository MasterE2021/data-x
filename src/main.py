# mian.py

import sys
from db_manager import DuckDBManager
from ui_manager import RowSlider
from ui_manager import TableView
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QFileDialog, QMessageBox
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QFont


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.btn = None
        self.table_view = None
        self.model = None
        self.db_manager = DuckDBManager()
        self.init_ui()

    def init_ui(self):
        # 创建主窗口
        self.setWindowTitle("data-x")
        self.resize(900, 600)

        # 创建中央部件和垂直布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 创建“点击导入数据”按钮
        self.btn = QPushButton("点击导入数据")
        self.btn.setFont(QFont("Arial", 12))
        self.btn.clicked.connect(self.read_data)  # 绑定点击事件
        layout.addWidget(self.btn)

        # 创建网格视图
        self.table_view = TableView()

        # 设置数据行滑块
        self.table_view.setVerticalScrollBar(RowSlider())

        # 创建数据模型并绑定到网格视图
        self.model = QStandardItemModel()
        self.table_view.setModel(self.model)

        layout.addWidget(self.table_view)

    def read_data(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "请选择数据文件",
            "",
            "Data Files (*.xls *.xlsx *.csv *.parquet)"
        )

        if not file_path:
            return

        try:
            rel = self.db_manager.query(f"select * from '{file_path}' limit 1000")
            columns = rel.columns
            result = rel.fetchall()
            self.model.clear()
            self.model.setHorizontalHeaderLabels(columns)

            for row in result:
                row_str = [str(item) if item is not None else "" for item in row]
                row_items = [QStandardItem(item) for item in row_str]
                self.model.appendRow(row_items)

            self.table_view.reset_cursor()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取文件失败: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
