# main.py

import sys
import os
from db_manager import DuckDBManager
from ui_manager import HomePage, DataViewPage
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QFileDialog, QMessageBox
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db_manager = DuckDBManager()
        self.file_list = []
        self._init_db()
        self.init_ui()

    def _init_db(self):
        """初始化数据库记录表，加载历史路径"""
        try:
            self.db_manager.query(
                "CREATE TABLE IF NOT EXISTS file_records (path TEXT PRIMARY KEY, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
            result = self.db_manager.query("SELECT path FROM file_records ORDER BY ts DESC")
            if hasattr(result, 'fetchall'):
                rows = result.fetchall()
            else:
                rows = list(result)
            self.file_list = [row[0] for row in rows]
        except Exception as e:
            print(f"数据库记录功能初始化失败：{e}，将仅使用内存记录")
            self.file_list = []

    def _save_record(self, path):
        """将路径保存到数据库和内存列表"""
        try:
            self.db_manager.query(f"INSERT OR IGNORE INTO file_records VALUES ('{path}')")
        except Exception as e:
            print(f"保存记录失败：{e}")
        if path in self.file_list:
            self.file_list.remove(path)
        self.file_list.insert(0, path)

    def init_ui(self):
        self.setWindowTitle("data-x")
        self.resize(900, 600)

        # 使用堆栈式布局管理两个页面
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # 创建页面实例
        self.home_page = HomePage()
        self.data_page = DataViewPage()

        self.stack.addWidget(self.home_page)   # index 0
        self.stack.addWidget(self.data_page)   # index 1

        # 连接信号
        self.home_page.import_requested.connect(self.on_import_requested)
        self.home_page.file_selected.connect(self.on_file_selected)
        self.data_page.back_requested.connect(self.on_back_requested)

        # 初始显示首页并刷新列表
        self.home_page.set_file_list(self.file_list)

    def on_import_requested(self):
        """处理导入新数据请求"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "请选择数据文件（可多选）",
            "",
            "Data Files (*.xls *.xlsx *.csv *.parquet)"
        )
        if not file_paths:
            return

        for path in file_paths:
            self._save_record(path)
        self.home_page.set_file_list(self.file_list)

    def on_file_selected(self, path):
        """加载选中的历史文件并切换到数据页"""
        try:
            rel = self.db_manager.query(f"select * from '{path}' limit 1000")
            columns = rel.columns
            rows = rel.fetchall()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取文件失败:\n{path}\n{e}")
            return

        self.data_page.display_data(columns, rows, os.path.basename(path))
        self.stack.setCurrentIndex(1)

    def on_back_requested(self):
        """返回首页"""
        self.stack.setCurrentIndex(0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())