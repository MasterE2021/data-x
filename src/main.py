# main.py

import sys
from db_manager import DuckDBManager
from ui_manager import RowSlider, TableView
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QMessageBox, QStackedWidget, QScrollArea,
    QLabel, QFrame
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QFont
from PySide6.QtCore import Qt


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.btn_import = None
        self.table_view = None
        self.row_slider = None
        self.model = None
        self.db_manager = DuckDBManager()

        # 用于存储已导入文件的路径列表（启动时从数据库加载）
        self.file_list = []
        self._init_db()
        self.init_ui()

    def _init_db(self):
        """初始化数据库，创建记录表，加载历史路径"""
        try:
            self.db_manager.query(
                "CREATE TABLE IF NOT EXISTS file_records (path TEXT PRIMARY KEY, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
            result = self.db_manager.query("SELECT path FROM file_records ORDER BY ts DESC")
            # DuckDB的query可能返回可迭代对象，尝试fetchall
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
        # 无论如何都更新内存列表，避免重复可放在前面
        if path not in self.file_list:
            self.file_list.insert(0, path)  # 最新的放在最前
        else:
            # 移到最前
            self.file_list.remove(path)
            self.file_list.insert(0, path)

    def init_ui(self):
        self.setWindowTitle("data-x")
        self.resize(900, 600)

        # 中央部件使用堆栈式布局
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # ========== 首页（数据表管理页） ==========
        self.home_page = QWidget()
        home_layout = QVBoxLayout(self.home_page)

        # 标题
        title = QLabel("📂 数据表管理")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        home_layout.addWidget(title)

        # 导入新数据按钮
        self.btn_import = QPushButton("📁 导入新数据")
        self.btn_import.setFont(QFont("Arial", 12))
        self.btn_import.clicked.connect(self.import_new_file)
        home_layout.addWidget(self.btn_import)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        home_layout.addWidget(line)

        # 历史文件区域（滚动）
        self.history_label = QLabel("📋 历史文件")
        self.history_label.setFont(QFont("Arial", 12, QFont.Bold))
        home_layout.addWidget(self.history_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.scroll_content)
        home_layout.addWidget(self.scroll_area)

        # 占位标签：无记录时显示
        self.placeholder_label = QLabel("暂无导入记录")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: gray; font-size: 14px;")

        # ========== 数据浏览页 ==========
        self.data_page = QWidget()
        data_layout = QVBoxLayout(self.data_page)

        # 顶部操作栏：返回按钮 + 当前文件名标签（可选）
        top_bar = QHBoxLayout()
        self.btn_back = QPushButton("← 返回首页")
        self.btn_back.clicked.connect(self.go_back_home)
        self.current_file_label = QLabel("")
        self.current_file_label.setFont(QFont("Arial", 10))
        top_bar.addWidget(self.btn_back)
        top_bar.addWidget(self.current_file_label)
        top_bar.addStretch()
        data_layout.addLayout(top_bar)

        # 表格与滑块区域（保持原有布局）
        h_layout = QHBoxLayout()
        self.table_view = TableView()
        self.row_slider = RowSlider()
        self.row_slider.setOrientation(Qt.Vertical)
        self.row_slider.setRange(0, 0)

        h_layout.addWidget(self.table_view)
        h_layout.addWidget(self.row_slider)
        data_layout.addLayout(h_layout)

        # 创建数据模型并绑定到表格
        self.model = QStandardItemModel()
        self.table_view.setModel(self.model)

        # 信号连接（只连接一次）
        self.table_view.cursor_row_changed.connect(self._on_cursor_row_changed)
        self.row_slider.valueChanged.connect(self._on_slider_value_changed)

        # 将两个页面加入堆栈
        self.stack.addWidget(self.home_page)  # index 0
        self.stack.addWidget(self.data_page)  # index 1

        # 刷新首页按钮（根据file_list）
        self.refresh_home_buttons()

    def refresh_home_buttons(self):
        """清空并重建历史文件按钮列表"""
        # 移除原有按钮和占位标签
        for i in reversed(range(self.scroll_layout.count())):
            widget = self.scroll_layout.itemAt(i).widget()
            if widget:
                self.scroll_layout.removeWidget(widget)
                widget.setParent(None)

        if not self.file_list:
            self.scroll_layout.addWidget(self.placeholder_label)
            return

        # 为每个文件创建一个带样式的按钮
        for path in self.file_list:
            # 提取文件名
            import os
            name = os.path.basename(path)
            btn = QPushButton(f"{name}\n{path}")
            btn.setFlat(True)
            btn.setStyleSheet(
                "QPushButton {"
                "   text-align: left;"
                "   padding: 8px;"
                "   border: 1px solid #ccc;"
                "   border-radius: 4px;"
                "   background: #f9f9f9;"
                "}"
                "QPushButton:hover {"
                "   background: #e0f0ff;"
                "}"
            )
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(50)
            # 点击按钮加载对应文件
            btn.clicked.connect(lambda checked=False, p=path: self.load_existing_file(p))
            self.scroll_layout.addWidget(btn)

    def import_new_file(self):
        """打开文件对话框导入新数据"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "请选择数据文件",
            "",
            "Data Files (*.xls *.xlsx *.csv *.parquet)"
        )
        if not file_path:
            return
        # 加载数据并切换到数据页
        self.load_data_from_file(file_path)
        # 记录到历史和数据库
        self._save_record(file_path)
        # 刷新首页按钮
        self.refresh_home_buttons()

    def load_existing_file(self, file_path):
        """加载已有的文件"""
        self.load_data_from_file(file_path)

    def load_data_from_file(self, file_path):
        """核心：查询文件数据并填充模型，显示数据页"""
        try:
            rel = self.db_manager.query(f"select * from '{file_path}' limit 1000")
            columns = rel.columns
            result = rel.fetchall()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取文件失败: {e}")
            return

        # 填充模型
        self.model.clear()
        self.model.setHorizontalHeaderLabels(columns)
        for row in result:
            row_str = [str(item) if item is not None else "" for item in row]
            row_items = [QStandardItem(item) for item in row_str]
            self.model.appendRow(row_items)

        # 更新滑块范围并重置游标
        max_row = max(0, len(result) - 1)
        self.row_slider.setRange(0, max_row)
        self.table_view.reset_cursor()

        # 显示当前文件名
        import os
        self.current_file_label.setText(f"当前文件：{os.path.basename(file_path)}")

        # 切换到数据浏览页
        self.stack.setCurrentIndex(1)

    def go_back_home(self):
        """返回首页"""
        self.stack.setCurrentIndex(0)

    def _on_cursor_row_changed(self, row):
        """表格游标移动后，同步滑块的值（屏蔽信号防止递归）"""
        self.row_slider.blockSignals(True)
        self.row_slider.setValue(row)
        self.row_slider.blockSignals(False)

    def _on_slider_value_changed(self, row):
        """用户拖拽滑块时，将游标移至对应行"""
        self.table_view.set_cursor_row(row)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
