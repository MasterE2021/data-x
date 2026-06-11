import sys
import os  # 引入 os 库，用于处理路径
import duckdb


# 封装独立的 DuckDB 管理类，负责初始化、离线插件加载和状态检查
class DuckDBManager:
    def __init__(self):
        # 在程序启动时，立刻在后台加载并初始化 DuckDB 连接
        self.conn = duckdb.connect()
        self._load_offline_extensions()

    def _load_offline_extensions(self):
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

    def query(self, sql_query):
        # 封装对外的统一查询接口
        return self.conn.query(sql_query)
