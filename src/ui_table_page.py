# ui_table_page.py

import os
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QMessageBox, QSpinBox, QDialog, QComboBox, QCheckBox,
    QDialogButtonBox, QFileDialog, QProgressDialog
)
from PySide6.QtCore import Signal, Qt, QThread
from PySide6.QtGui import QStandardItemModel, QStandardItem, QFont

from ui_manager import TableView, RowSlider
from ui_table_filter import FilterDialog, FilterConditionNode, FilterGroupNode
from ui_column_selector import ColumnSelectorDialog


# -------------------- 导出线程 --------------------
class ExportThread(QThread):
    """后台导出：使用 COPY (SELECT ... FROM '源文件') TO '目标路径'"""
    progress = Signal(int)
    finished = Signal()
    error = Signal(str)

    def __init__(self, db_manager, source_path, file_path, fmt, columns, where_clause="", parent=None):
        super().__init__(parent)
        self.source_path = source_path
        self.file_path = file_path
        self.fmt = fmt
        self.columns = columns
        self.where_clause = where_clause
        self.db_manager = db_manager
        self._is_canceled = False

    def run(self):
        try:
            self._export_from_source()
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        self._is_canceled = True

    def _export_from_source(self):
        con = self.db_manager.conn
        try:
            safe_columns = [f'"{col}"' for col in self.columns]
            col_defs = ", ".join(safe_columns)

            select_sql = f"select {col_defs} from '{self.source_path}' with (format {self.fmt}, header true)"
            if self.where_clause.strip():
                select_sql += f" where {self.where_clause}"

            # 直接根据文件扩展名导出，并包含列标题
            copy_sql = f"copy ({select_sql}) to '{self.file_path}'"
            con.execute(copy_sql)
            self.progress.emit(100)
        except Exception as e:
            print(f"导出失败：{e}")
        finally:
            con.close()


# -------------------- 筛选线程 --------------------
class FilterThread(QThread):
    progress = Signal(int)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, rows, columns, root_node, parent=None):
        super().__init__(parent)
        self.rows = rows
        self.columns = columns
        self.root_node = root_node
        self._is_canceled = False

    def run(self):
        try:
            total = len(self.rows)
            filtered = []
            for i, row in enumerate(self.rows):
                if self._is_canceled:
                    return
                if self._eval_node(self.root_node, row):
                    filtered.append(row)
                if i % max(1, total // 100) == 0:
                    self.progress.emit(int(i / total * 100))
            self.finished.emit(filtered)
        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        self._is_canceled = True

    def _eval_node(self, node, row):
        if isinstance(node, FilterConditionNode):
            return self._eval_condition(node, row)
        elif isinstance(node, FilterGroupNode):
            if not node.enabled or not node.children:
                return True
            results = [self._eval_node(child, row) for child in node.children]
            final = results[0]
            for i in range(1, len(results)):
                conn = node.connectors[i - 1].upper()
                if conn == "AND":
                    final = final and results[i]
                else:
                    final = final or results[i]
            return final
        return True

    def _eval_condition(self, cond, row):
        if not cond.enabled:
            return True
        col_idx = self.columns.index(cond.column) if cond.column in self.columns else -1
        if col_idx == -1:
            return True
        cell = row[col_idx]
        op = cond.operator
        val = cond.value

        if op == "is_null":
            return cell is None or str(cell).strip() == ""
        if op == "is_not_null":
            return cell is not None and str(cell).strip() != ""

        cell_str = str(cell) if cell is not None else ""
        val_str = str(val) if val is not None else ""

        if op == "==":
            return cell_str == val_str
        elif op == "!=":
            return cell_str != val_str
        elif op in (">", "<", ">=", "<="):
            try:
                num_cell = float(cell_str)
                num_val = float(val_str)
            except ValueError:
                return False
            if op == ">": return num_cell > num_val
            if op == "<": return num_cell < num_val
            if op == ">=": return num_cell >= num_val
            if op == "<=": return num_cell <= num_val
        elif op == "icontains":
            return val_str.lower() in cell_str.lower()
        elif op == "contains":
            return val_str in cell_str
        elif op == "not_contains":
            return val_str not in cell_str
        return True


# -------------------- 导出对话框 --------------------
class ExportDialog(QDialog):
    FORMATS = {
        "CSV (*.csv)": "csv",
        "Excel (.xlsx)": "xlsx",
        "Excel 97-2003 (.xls)": "xls",
        "Parquet (*.parquet)": "parquet",
    }
    ROW_LIMITS = {
        "xls": 65536,
        "xlsx": 1048576,
        "csv": 10000000,
        "parquet": float("inf"),
    }

    def __init__(self, row_count, parent=None):
        super().__init__(parent)
        self.row_count = row_count
        self.setWindowTitle("导出数据")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("导出格式:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(list(self.FORMATS.keys()))
        layout.addWidget(self.format_combo)

        self.info_label = QLabel(f"当前数据行数: {self.row_count}")
        layout.addWidget(self.info_label)

        self.warning_label = QLabel()
        self.warning_label.setStyleSheet("color: red")
        layout.addWidget(self.warning_label)
        self.update_warning()
        self.format_combo.currentIndexChanged.connect(self.update_warning)

        self.filter_check = QCheckBox("仅导出当前筛选结果")
        self.filter_check.setChecked(True)
        layout.addWidget(self.filter_check)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def update_warning(self):
        fmt_key = self.format_combo.currentText()
        fmt = self.FORMATS[fmt_key]
        limit = self.ROW_LIMITS[fmt]
        if self.row_count > limit:
            self.warning_label.setText(
                f"警告：行数 {self.row_count} 超过 {fmt} 建议上限 {limit}，"
                "可能导致导出失败或数据丢失，请选择其他格式。"
            )
        else:
            self.warning_label.clear()

    def validate_and_accept(self):
        fmt_key = self.format_combo.currentText()
        fmt = self.FORMATS[fmt_key]
        limit = self.ROW_LIMITS[fmt]
        if self.row_count > limit:
            reply = QMessageBox.warning(
                self, "行数超限",
                f"即将导出的行数 ({self.row_count}) 超出 {fmt} 的建议最大行数 ({limit})。\n"
                "是否仍要导出？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        self.accept()

    def selected_format(self):
        return self.FORMATS[self.format_combo.currentText()]

    def selected_filter_only(self):
        return self.filter_check.isChecked()


# -------------------- 数据浏览页 --------------------
class DataViewPage(QWidget):
    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_columns = []
        self.original_rows = []
        self.current_data = []
        self.visible_column_indices = []
        self.page_size = 1000
        self.current_page = 0
        self.current_filter_root = None
        self.source_file_path = None
        self.source_file_name = ""
        self.db_manager = None
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # 顶部工具栏
        top_layout = QHBoxLayout()
        self.btn_back = QPushButton("← 返回首页")
        self.btn_back.clicked.connect(self.back_requested.emit)
        top_layout.addWidget(self.btn_back)

        self.current_file_label = QLabel("")
        self.current_file_label.setFont(QFont("Arial", 10))
        top_layout.addWidget(self.current_file_label)

        self.lbl_stats = QLabel("")
        top_layout.addWidget(self.lbl_stats)
        top_layout.addStretch()

        self.btn_select_columns = QPushButton("📊 选择列")
        self.btn_select_columns.clicked.connect(self.open_column_selector)
        top_layout.addWidget(self.btn_select_columns)

        self.btn_filter = QPushButton("🔍 高级筛选")
        self.btn_filter.clicked.connect(self.open_filter_dialog)
        top_layout.addWidget(self.btn_filter)

        self.btn_export = QPushButton("💾 导出")
        self.btn_export.clicked.connect(self.export_data)
        top_layout.addWidget(self.btn_export)
        main_layout.addLayout(top_layout)

        # 表格与滑块
        table_slider_layout = QHBoxLayout()
        self.table_view = TableView()
        self.model = QStandardItemModel()
        self.table_view.setModel(self.model)
        self.table_view.cursor_row_changed.connect(self.on_cursor_row_changed)
        table_slider_layout.addWidget(self.table_view)

        self.slider = RowSlider()
        self.slider.valueChanged.connect(self.on_slider_changed)
        table_slider_layout.addWidget(self.slider)
        main_layout.addLayout(table_slider_layout)

        # 分页控件
        page_layout = QHBoxLayout()
        self.btn_first = QPushButton("首页")
        self.btn_first.clicked.connect(self.go_first)
        self.btn_prev = QPushButton("上一页")
        self.btn_prev.clicked.connect(self.go_prev)
        self.page_input = QSpinBox()
        self.page_input.setMinimum(1)
        self.page_input.setMaximum(1)
        self.page_input.setPrefix("第 ")
        self.page_input.setSuffix(" 页")
        self.page_input.valueChanged.connect(self.go_to_page)
        self.btn_next = QPushButton("下一页")
        self.btn_next.clicked.connect(self.go_next)
        self.btn_last = QPushButton("末页")
        self.btn_last.clicked.connect(self.go_last)

        page_layout.addWidget(self.btn_first)
        page_layout.addWidget(self.btn_prev)
        page_layout.addWidget(self.page_input)
        page_layout.addWidget(self.btn_next)
        page_layout.addWidget(self.btn_last)
        page_layout.addStretch()
        main_layout.addLayout(page_layout)

    def display_data(self, source_path, columns, rows, file_name, query_elapsed_ms):
        self.original_columns = columns
        self.original_rows = rows
        self.current_data = rows
        self.visible_column_indices = list(range(len(columns)))
        self.current_file_label.setText(f"当前文件：{file_name}")
        self.source_file_path = source_path
        self.source_file_name = file_name  # 保存文件名，用于导出默认名
        self.current_page = 0
        self.current_filter_root = None
        self._show_current_page()
        self._update_stats(len(rows), len(rows), query_elapsed_ms)
        self._update_pagination_state()

    def _show_current_page(self):
        self.model.clear()
        visible_headers = [self.original_columns[i] for i in self.visible_column_indices]
        self.model.setHorizontalHeaderLabels(visible_headers)

        start = self.current_page * self.page_size
        end = min(start + self.page_size, len(self.current_data))
        page_rows = self.current_data[start:end]

        for row_data in page_rows:
            items = [QStandardItem(str(row_data[i])) for i in self.visible_column_indices]
            self.model.appendRow(items)

        self.table_view.reset_cursor()
        self.slider.setMinimum(0)
        self.slider.setMaximum(max(0, len(page_rows) - 1))
        self.slider.setValue(0)

    def _update_stats(self, total, filtered, elapsed):
        self.lbl_stats.setText(f"总行数: {total} | 筛选后: {filtered} | 耗时: {elapsed:.1f} ms")

    def _update_pagination_state(self):
        total_pages = max(1, (len(self.current_data) + self.page_size - 1) // self.page_size)
        self.page_input.setMaximum(total_pages)
        self.page_input.setValue(self.current_page + 1)
        self.btn_first.setEnabled(self.current_page > 0)
        self.btn_prev.setEnabled(self.current_page > 0)
        self.btn_next.setEnabled(self.current_page < total_pages - 1)
        self.btn_last.setEnabled(self.current_page < total_pages - 1)

    def on_cursor_row_changed(self, row):
        self.slider.blockSignals(True)
        self.slider.setValue(row)
        self.slider.blockSignals(False)

    def on_slider_changed(self, value):
        if 0 <= value < self.model.rowCount():
            self.table_view.set_cursor_row(value)

    def go_first(self):
        self.current_page = 0
        self._show_current_page()
        self._update_pagination_state()

    def go_prev(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._show_current_page()
            self._update_pagination_state()

    def go_next(self):
        total_pages = max(1, (len(self.current_data) + self.page_size - 1) // self.page_size)
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self._show_current_page()
            self._update_pagination_state()

    def go_last(self):
        total_pages = max(1, (len(self.current_data) + self.page_size - 1) // self.page_size)
        self.current_page = total_pages - 1
        self._show_current_page()
        self._update_pagination_state()

    def go_to_page(self, page_no):
        page_no = max(1, min(page_no, self.page_input.maximum()))
        self.current_page = page_no - 1
        self._show_current_page()
        self._update_pagination_state()

    # ---- 列筛选 ----
    def open_column_selector(self):
        if not self.original_columns:
            return
        dlg = ColumnSelectorDialog(self.original_columns, self.visible_column_indices, self)
        if dlg.exec() == QDialog.Accepted:
            new_indices = dlg.get_selected_indices()
            if not new_indices:
                return
            self.visible_column_indices = new_indices
            self._show_current_page()
            self._update_pagination_state()

    # ---- 高级筛选 ----
    def open_filter_dialog(self):
        if not self.original_columns:
            return
        dlg = FilterDialog(self.original_columns, self, self.current_filter_root)
        dlg.filterApplied.connect(self.apply_filter)
        dlg.exec()

    def apply_filter(self, root_node):
        self.current_filter_root = root_node
        self.filter_thread = FilterThread(self.original_rows, self.original_columns, root_node)
        progress = QProgressDialog("正在筛选...", "取消", 0, 100, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        self.filter_thread.progress.connect(progress.setValue)
        self.filter_thread.finished.connect(
            lambda result: self._on_filter_finished(progress, result)
        )
        self.filter_thread.error.connect(
            lambda msg: self._on_filter_error(progress, msg)
        )
        progress.canceled.connect(self.filter_thread.cancel)
        self.filter_thread.start()

    def _on_filter_finished(self, progress, filtered_rows):
        progress.close()
        self.current_data = filtered_rows
        self.current_page = 0
        self._show_current_page()
        self._update_stats(len(self.original_rows), len(filtered_rows), 0)
        self._update_pagination_state()

    def _on_filter_error(self, progress, msg):
        progress.close()
        QMessageBox.warning(self, "筛选错误", msg)

    # ---- 导出 ----
    def export_data(self):
        if not self.original_columns or not self.current_data:
            return

        if not self.source_file_path:
            QMessageBox.warning(self, "导出错误", "未找到源文件路径，无法导出。")
            return

        # 预估行数（用于对话框提示）
        display_rows = len(self.current_data) if self.current_filter_root else len(self.original_rows)
        export_dlg = ExportDialog(row_count=display_rows, parent=self)
        if export_dlg.exec() != QDialog.Accepted:
            return

        fmt = export_dlg.selected_format()
        filter_only = export_dlg.selected_filter_only()

        # 可见列
        columns_to_export = [self.original_columns[i] for i in self.visible_column_indices]

        # 构造 WHERE 条件
        where_clause = ""
        if filter_only and self.current_filter_root:
            where_clause = self._filter_to_sql(self.current_filter_root)
            if where_clause is None:
                QMessageBox.information(self, "提示", "复杂筛选条件无法转为 SQL，将导出当前内存中的筛选结果。")
                # 回退内存导出（此处仅作提示，可扩展）
                where_clause = ""
        elif not filter_only:
            where_clause = ""

        # ---------- 生成默认文件名 ----------
        # 获取不带扩展名的基本文件名
        base_name = "export"  # 默认值
        if self.source_file_name:
            base_name = os.path.splitext(self.source_file_name)[0]
        elif self.source_file_path:
            base_name = os.path.splitext(os.path.basename(self.source_file_path))[0]

        # 时间戳
        time_str = datetime.now().strftime("%Y%m%d%H%M")

        # 格式后缀映射
        fmt_suffix = {
            "csv": ".csv",
            "xlsx": ".xlsx",
            "xls": ".xls",
            "parquet": ".parquet"
        }
        default_name = f"{base_name}_{time_str}{fmt_suffix.get(fmt, '.csv')}"

        file_filters = {
            "csv": "CSV Files (*.csv)",
            "xlsx": "Excel Files (*.xlsx)",
            "xls": "Excel Files (*.xls)",
            "parquet": "Parquet Files (*.parquet)",
        }
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存文件", default_name, file_filters.get(fmt, "All Files (*)")
        )
        if not file_path:
            return

        # 启动导出线程
        self.export_thread = ExportThread(
            db_manager=self.db_manager,
            source_path=self.source_file_path,
            file_path=file_path,
            fmt=fmt,
            columns=columns_to_export,
            where_clause=where_clause
        )
        progress = QProgressDialog("正在导出...", "取消", 0, 100, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        self.export_thread.progress.connect(progress.setValue)
        self.export_thread.finished.connect(lambda: self._on_export_finished(progress))
        self.export_thread.error.connect(lambda msg: self._on_export_error(progress, msg))
        progress.canceled.connect(self.export_thread.cancel)
        self.export_thread.start()

    def _export_from_memory(self, fmt, columns_to_export, rows):
        """当无法使用 SQL 直接导出时，回退到内存插入方式的导出（预留）"""
        QMessageBox.information(self, "回退导出", "即将使用内存方式导出，大数据量可能较慢。")
        # 可扩展为实际的内存导出线程

    def _filter_to_sql(self, root_node):
        try:
            return self._node_to_sql(root_node)
        except Exception:
            return None

    def _node_to_sql(self, node):
        if isinstance(node, FilterConditionNode):
            if not node.enabled:
                return "1=1"
            col = node.column
            op = node.operator
            val = node.value
            if op == "==":
                return f'"{col}" = {self._quote(val)}'
            elif op == "!=":
                return f'"{col}" != {self._quote(val)}'
            elif op == ">":
                return f'"{col}" > {self._quote(val)}'
            elif op == "<":
                return f'"{col}" < {self._quote(val)}'
            elif op == ">=":
                return f'"{col}" >= {self._quote(val)}'
            elif op == "<=":
                return f'"{col}" <= {self._quote(val)}'
            elif op == "contains":
                return f'"{col}" LIKE {self._quote(f"%{val}%")}'
            elif op == "not_contains":
                return f'"{col}" NOT LIKE {self._quote(f"%{val}%")}'
            elif op == "icontains":
                return f'"{col}" ILIKE {self._quote(f"%{val}%")}'
            elif op == "is_null":
                return f'"{col}" IS NULL'
            elif op == "is_not_null":
                return f'"{col}" IS NOT NULL'
            else:
                return "1=1"
        elif isinstance(node, FilterGroupNode):
            if not node.enabled or not node.children:
                return "1=1"
            parts = []
            for i, child in enumerate(node.children):
                parts.append(self._node_to_sql(child))
                if i < len(node.children) - 1:
                    parts.append(node.connectors[i])
            return "(" + " ".join(parts) + ")"
        return "1=1"

    def _quote(self, value):
        if value is None:
            return "NULL"
        if isinstance(value, (int, float)):
            return str(value)
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"

    def _on_export_finished(self, progress):
        progress.close()
        QMessageBox.information(self, "导出完成", "数据已成功导出。")

    def _on_export_error(self, progress, msg):
        progress.close()
        QMessageBox.critical(self, "导出失败", msg)
