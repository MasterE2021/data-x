# main.py

import sys
import os
from db_manager import DuckDBManager, SQLiteManager
from ui_manager import HomePage, DataViewPage
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QFileDialog, QMessageBox
)


class MainWindow(QMainWindow):
    """主窗口：负责页面调度、数据加载和文件记录管理。"""

    def __init__(self):
        super().__init__()
        self.db_manager = DuckDBManager()

        data_dir = os.path.join(os.path.expanduser("~"), ".data-x")
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, "dx-file.data")
        self.record_db = SQLiteManager(db_path)

        self.file_list = self.record_db.get_records()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("data-x")
        self.resize(900, 600)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.home_page = HomePage()
        self.data_page = DataViewPage()

        self.stack.addWidget(self.home_page)  # index 0
        self.stack.addWidget(self.data_page)  # index 1

        self.home_page.import_requested.connect(self.on_import_requested)
        self.home_page.file_selected.connect(self.on_file_selected)
        self.data_page.back_requested.connect(self.on_back_requested)

        self.home_page.set_file_list(self.file_list)

    def on_import_requested(self):
        """处理导入新数据（多选），仅记录到首页。"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "请选择数据文件（可多选）",
            "",
            "Data Files (*.xls *.xlsx *.csv *.parquet)"
        )
        if not file_paths:
            return

        for path in file_paths:
            self.record_db.add_record(path)
        self.file_list = self.record_db.get_records()
        self.home_page.set_file_list(self.file_list)

    def on_file_selected(self, path):
        """用户点击首页文件按钮后，加载全表数据并切换到数据浏览页。"""
        try:
            start_time = __import__('time').time()
            # 不再限制行数，直接加载全表
            rel = self.db_manager.query(f"SELECT * FROM '{path}'")
            columns = rel.columns
            rows = rel.fetchall()
            elapsed = (__import__('time').time() - start_time) * 1000  # 毫秒

            self.data_page.display_data(columns, rows, os.path.basename(path), elapsed)
            self.stack.setCurrentIndex(1)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取文件失败:\n{path}\n{e}")
            return

    def on_back_requested(self):
        """返回首页。"""
        self.stack.setCurrentIndex(0)

    def closeEvent(self, event):
        """程序退出时关闭持久化连接。"""
        self.record_db.close()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
