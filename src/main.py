import sys
import os  # 引入 os 库，用于处理路径
import duckdb
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QTableView, QFileDialog, QMessageBox
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QFont


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # 在程序启动时，立刻在后台加载并初始化 DuckDB 连接
        self.conn = duckdb.connect()

        # --- 离线插件加载逻辑 ---
        # 定义需要加载的离线插件名称数组
        required_extensions = ["excel.duckdb_extension", "postgres_scanner.duckdb_extension"]

        # 完美兼容脚本和单文件 exe：如果是 exe 则直接用官方解压根目录 sys._MEIPASS，否则用脚本向上推导的根目录
        root_dir = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))
        ext_dir = os.path.join(root_dir, "lib")

        # 循环遍历数组，强制检查并加载每一个插件
        for ext_name in required_extensions:
            # 拼接出当前插件的绝对路径
            ext_path = os.path.join(ext_dir, ext_name)

            # 如果文件里面没有找到插件文件，直接抛出异常报错，中断程序
            if not os.path.exists(ext_path):
                raise FileNotFoundError(f"缺少关键离线插件文件: '{ext_name}'，路径应为: '{ext_path}'")

            # 修复 Python 3.11 下 f-string 内不能含反斜杠的问题
            safe_path = ext_path.replace('\\', '/')
            # 显式使用 LOAD 语法加载特定路径下的插件
            self.conn.query(f"load '{safe_path}'")
        # ------------------------

        # --- 检查 DuckDB 已成功加载的插件逻辑 ---
        # 查询系统元数据表 duckdb_extensions()，筛选出 loaded 为 true 的插件名称
        check_sql = "select extension_name from duckdb_extensions() where loaded = true"

        loaded_ext = self.conn.query(check_sql).fetchall()
        # 将查询结果（元组列表）平铺转换为纯文本列表
        loaded_extensions = [row[0] for row in loaded_ext]
        # 在控制台打印出来，方便开发和调试时确认状态
        print(f"--- DuckDB 离线初始化成功！当前已成功加载的插件列表: {loaded_extensions} ---")
        # ------------------------

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
            rel = self.conn.query(f"select * from '{file_path}' limit 10000")

            # 获取表头（列名）与行数据
            columns = rel.columns
            result = rel.fetchall()

            # 清空网格原有的内容和表头
            self.model.clear()
            self.model.setHorizontalHeaderLabels(columns)

            for row in result:
                # DuckDB 返回的每行是 tuple，需转换为字符串列表
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
