# db_manager.py

import sys
import os
import sqlite3
import duckdb


class SQLiteManager:
    """
    基于 SQLite 的文件路径持久化管理器。
    负责创建/读取用户目录下的 .data-x/dx-file.data 文件，
    提供记录增删查等操作。
    """

    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        # 启用 WAL 模式提升并发写入性能
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._create_table()

    def _create_table(self):
        """创建记录表（如果不存在）"""
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS file_records "
            "(path TEXT PRIMARY KEY, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        self.conn.commit()

    def add_record(self, path):
        """插入或更新文件路径记录（自动更新时间戳），并立即提交。"""
        self.conn.execute(
            "INSERT OR REPLACE INTO file_records (path, ts) VALUES (?, CURRENT_TIMESTAMP)",
            (path,)
        )
        self.conn.commit()

    def get_records(self):
        """返回按时间倒序排列的文件路径列表。"""
        cursor = self.conn.execute("SELECT path FROM file_records ORDER BY ts DESC")
        return [row[0] for row in cursor.fetchall()]

    def close(self):
        """关闭数据库连接。"""
        self.conn.close()


class DuckDBManager:
    """DuckDB 内存模式管理器，用于高效查询数据文件（Excel/CSV/Parquet 等）。
    自动加载离线插件以确保在只读环境（如 PyInstaller exe）中可用。
    """

    def __init__(self):
        self.conn = duckdb.connect()
        self._load_offline_extensions()

    def _load_offline_extensions(self):
        required_extensions = ["excel.duckdb_extension", "postgres_scanner.duckdb_extension"]

        # 自适应获取插件根目录：exe 时用 sys._MEIPASS，否则向上推导至项目根
        root_dir = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))
        ext_dir = os.path.join(root_dir, "lib")

        for ext_name in required_extensions:
            ext_path = os.path.join(ext_dir, ext_name)
            if not os.path.exists(ext_path):
                raise FileNotFoundError(f"缺少关键离线插件文件: '{ext_name}'，路径应为: '{ext_path}'")

            safe_path = ext_path.replace('\\', '/')
            self.conn.query(f"load '{safe_path}'")

        loaded_ext = self.conn.query(
            "SELECT extension_name FROM duckdb_extensions() WHERE loaded = true"
        ).fetchall()
        print(f"--- DuckDB 已成功加载的插件: {[row[0] for row in loaded_ext]} ---")

    def query(self, sql_query):
        """统一查询接口，返回 DuckDB 结果对象。"""
        return self.conn.query(sql_query)
