import sys
from db_manager import DuckDBManager
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QTableView, QFileDialog, QMessageBox
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QFont


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # 通过独立的类初始化 DuckDB 逻辑块
        self.db_manager = DuckDBManager()

        # 调用专门的界面布局函数搭建 GUI 结构，与交互函数实现物理分离
        self.init_ui()

    def init_ui(self):
        """专门负责 GUI 的控件声明、样式调整和布局组装（方便时常微调界面）"""
        # 创建主窗口
        self.setWindowTitle("CSV 导入工具")
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

        # 创建类似 Excel 的网格视图
        self.table_view = QTableView()
        layout.addWidget(self.table_view)

        # 创建数据模型并绑定到网格视图
        self.model = QStandardItemModel()
        self.table_view.setModel(self.model)

    def read_data(self):
        """专门负责业务逻辑交互：弹出对话框、调用 DuckDB 读取数据并填充网格"""
        # 弹出文件选择对话框，限制只能选择指定后缀的文件
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "请选择数据文件",
            "",
            "Data Files (*.xls *.xlsx *.csv *.parquet)"
        )

        # 如果用户没有选择文件，直接返回
        if not file_path:
            return

        try:
            # 使用启动时就已经加载好的 DuckDB 连接查询并读取选中的文件
            rel = self.db_manager.query(f"select * from '{file_path}' limit 10000")

            # 获取表头（列名）与行数据
            columns = rel.columns
            result = rel.fetchall()

            # 清空网格原有的内容和表头
            self.model.clear()
            self.model.setHorizontalHeaderLabels(columns)

            for row in result:
                # DuckDB 返回的每行 is tuple，需转换为字符串列表
                row_str = [str(item) if item is not None else "" for item in row]

                # 将每一行数据包装为 QStandardItem 并追加到表格模型中
                row_items = [QStandardItem(item) for item in row_str]
                self.model.appendRow(row_items)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取文件失败: {e}")


# 启动界面
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
