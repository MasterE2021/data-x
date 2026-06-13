# main.py

import sys
from db_manager import DuckDBManager
from ui_manager import RowSlider, TableView
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QMessageBox
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QFont
from PySide6.QtCore import Qt


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.btn = None
        self.table_view = None
        self.row_slider = None
        self.model = None
        self.db_manager = DuckDBManager()
        self.init_ui()

    def init_ui(self):
        # 主窗口
        self.setWindowTitle("data-x")
        self.resize(900, 600)

        # 中央部件和垂直布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 导入数据按钮
        self.btn = QPushButton("点击导入数据")
        self.btn.setFont(QFont("Arial", 12))
        self.btn.clicked.connect(self.read_data)
        layout.addWidget(self.btn)

        # 网格视图与游标滑块的组合布局
        h_layout = QHBoxLayout()
        self.table_view = TableView()
        self.row_slider = RowSlider()
        self.row_slider.setOrientation(Qt.Vertical)

        # 滑块范围初始设置（数据加载后会更新）
        self.row_slider.setRange(0, 0)

        h_layout.addWidget(self.table_view)
        h_layout.addWidget(self.row_slider)
        layout.addLayout(h_layout)

        # 创建数据模型并绑定到网格视图
        self.model = QStandardItemModel()
        self.table_view.setModel(self.model)

        # 1. 表格游标变化 → 更新滑块位置（避免循环）
        self.table_view.cursor_row_changed.connect(self._on_cursor_row_changed)
        # 2. 滑块被拖拽 → 设置表格游标
        self.row_slider.valueChanged.connect(self._on_slider_value_changed)

    def _on_cursor_row_changed(self, row):
        """表格游标移动后，同步滑块的值（屏蔽信号防止递归）"""
        self.row_slider.blockSignals(True)
        self.row_slider.setValue(row)
        self.row_slider.blockSignals(False)

    def _on_slider_value_changed(self, row):
        """用户拖拽滑块时，将游标移至对应行"""
        # 不发出 cursor_row_changed，避免再次更新滑块（造成抖动）
        self.table_view.set_cursor_row(row)

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

            # 更新滑块范围：0 到 行数-1
            max_row = max(0, len(result) - 1)
            self.row_slider.setRange(0, max_row)
            # 重置游标到第一行，同时会触发信号更新滑块
            self.table_view.reset_cursor()

        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取文件失败: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
