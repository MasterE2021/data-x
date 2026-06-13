# main.py

import sys
import os
import sqlite3
from db_manager import DuckDBManager
from ui_manager import HomePage, DataViewPage
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QFileDialog, QMessageBox
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # 原有的内存模式连接，用于查询数据文件
        self.db_manager = DuckDBManager()

        # 构建用户数据目录 ~/.data-x
        self.data_dir = os.path.join(os.path.expanduser("~"), ".data-x")
        os.makedirs(self.data_dir, exist_ok=True)
        db_path = os.path.join(self.data_dir, "file_records.db")

        # 使用 sqlite3 做持久化（替代 DuckDB 文件模式）
        self.record_conn = sqlite3.connect(db_path)
        self.record_conn.execute("PRAGMA journal_mode=WAL")  # 可选，提升并发性能
        self.file_list = []
        self._init_db()
        self.init_ui()

    def _init_db(self):
        """初始化记录表，加载历史路径"""
        try:
            self.record_conn.execute(
                "CREATE TABLE IF NOT EXISTS file_records (path TEXT PRIMARY KEY, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
            self.record_conn.commit()
            cursor = self.record_conn.execute(
                "SELECT path FROM file_records ORDER BY ts DESC"
            )
            self.file_list = [row[0] for row in cursor.fetchall()]
        except Exception as e:
            print(f"持久化记录初始化失败：{e}，将使用空列表")
            self.file_list = []

    def _save_record(self, path):
        """将路径保存到数据库和内存列表"""
        try:
            self.record_conn.execute(
                "INSERT OR REPLACE INTO file_records (path, ts) VALUES (?, CURRENT_TIMESTAMP)",
                (path,)
            )
            self.record_conn.commit()
        except Exception as e:
            print(f"保存记录失败：{e}")
        # 更新内存列表
        if path in self.file_list:
            self.file_list.remove(path)
        self.file_list.insert(0, path)

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
        """处理导入新数据请求（多选）"""
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

    def closeEvent(self, event):
        """关闭连接"""
        self.record_conn.close()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
