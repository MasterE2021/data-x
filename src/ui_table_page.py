# ui_table_page.py

import duckdb
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


# -------------------- 导出线程（统一使用 DuckDB COPY）--------------------
class ExportThread(QThread):
    """后台导出：将内存数据插入 DuckDB 临时表，再用 COPY 导出为指定格式"""
    progress = Signal(int)
    finished = Signal()
    error = Signal(str)

    # 格式映射到 DuckDB COPY 的 FORMAT 参数
    FORMAT_MAP = {
        "csv": "CSV",
        "xlsx": "XLSX",
        "xls": "XLS",
        "parquet": "PARQUET",
    }

    def __init__(self, file_path, fmt, rows, columns, col_indices, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.fmt = fmt
        self.rows = rows
        self.columns = columns  # 导出的列名列表
        self.col_indices = col_indices  # 原始行中对应列的索引
        self._is_canceled = False

    def run(self):
        try:
            self._export_with_duckdb()
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        self._is_canceled = True

    def _export_with_duckdb(self):
        con = duckdb.connect()
        try:
            # 构建临时表，列名可能包含特殊字符，采用双引号包裹
            safe_columns = [f'"{col}"' for col in self.columns]
            col_defs = ", ".join(f"{c} VARCHAR" for c in safe_columns)
            con.execute(f"CREATE TEMP TABLE export_data ({col_defs})")

            total = len(self.rows)
            batch = []
            placeholders = ",".join("?" * len(self.col_indices))
            for i, row in enumerate(self.rows):
                if self._is_canceled:
                    return
                batch.append(tuple(row[j] for j in self.col_indices))
                if len(batch) >= 5000:
                    con.executemany(
                        f"INSERT INTO export_data VALUES ({placeholders})",
                        batch
                    )
                    batch.clear()
                    self.progress.emit(int(i / total * 100))
            if batch:
                con.executemany(
                    f"INSERT INTO export_data VALUES ({placeholders})",
                    batch
                )

            # 拼接 COPY 命令，指定格式
            duckdb_format = self.FORMAT_MAP.get(self.fmt, "CSV")
            copy_sql = (
                f"COPY export_data TO '{self.file_path}' "
                f"(FORMAT {duckdb_format}, HEADER TRUE)"
            )
            con.execute(copy_sql)
            self.progress.emit(100)
        finally:
            con.close()


# -------------------- 筛选线程（可选）--------------------
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

    def display_data(self, columns, rows, file_name, query_elapsed_ms):
        self.original_columns = columns
        self.original_rows = rows
        self.current_data = rows
        self.visible_column_indices = list(range(len(columns)))
        self.current_file_label.setText(f"当前文件：{file_name}")
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

        # 预估行数供对话框使用（用户可能切换范围，此处先以当前筛选数据为准）
        display_rows = len(self.current_data) if self.current_filter_root else len(self.original_rows)
        export_dlg = ExportDialog(row_count=display_rows, parent=self)
        if export_dlg.exec() != QDialog.Accepted:
            return

        fmt = export_dlg.selected_format()
        filter_only = export_dlg.selected_filter_only()

        rows_to_export = self.current_data if filter_only else self.original_rows
        col_indices = self.visible_column_indices
        columns_to_export = [self.original_columns[i] for i in col_indices]

        # 文件保存对话框
        file_filters = {
            "csv": "CSV Files (*.csv)",
            "xlsx": "Excel Files (*.xlsx)",
            "xls": "Excel Files (*.xls)",
            "parquet": "Parquet Files (*.parquet)",
        }
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存文件", "", file_filters.get(fmt, "All Files (*)")
        )
        if not file_path:
            return

        # 启动导出线程（纯 DuckDB）
        self.export_thread = ExportThread(
            file_path, fmt, rows_to_export, columns_to_export, col_indices
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

    def _on_export_finished(self, progress):
        progress.close()
        QMessageBox.information(self, "导出完成", "数据已成功导出。")

    def _on_export_error(self, progress, msg):
        progress.close()
        QMessageBox.critical(self, "导出失败", msg)
