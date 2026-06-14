# ui_table_page.py

import time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox, QSpinBox
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QStandardItemModel, QStandardItem, QFont

from ui_manager import TableView, RowSlider
from ui_table_filter import FilterDialog, FilterConditionNode, FilterGroupNode


class DataViewPage(QWidget):
    """数据浏览页：展示表格数据、分页导航、高级筛选功能。"""
    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_columns = []
        self.original_rows = []
        self.current_data = []
        self.page_size = 1000
        self.current_page = 0
        self.query_elapsed_ms = 0
        self.current_filter_root = None  # 保存筛选状态
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

        self.btn_filter = QPushButton("🔍 高级筛选")
        self.btn_filter.clicked.connect(self.open_filter_dialog)
        top_layout.addWidget(self.btn_filter)
        main_layout.addLayout(top_layout)

        # 表格视图与滑块组合
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
        self.page_input.lineEdit().setReadOnly(True)  # 但允许输入跳转？
        self.page_input.lineEdit().setReadOnly(False)  # 允许直接输入页码
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
        """加载全量数据并显示第一页。"""
        self.original_columns = columns
        self.original_rows = rows
        self.current_data = rows  # 初始未筛选
        self.current_file_label.setText(f"当前文件：{file_name}")
        self.current_page = 0
        self.current_filter_root = None
        self._show_current_page()
        self._update_stats(len(rows), len(rows), query_elapsed_ms)
        self._update_pagination_state()

    def _show_current_page(self):
        """渲染当前页的数据到表格模型。"""
        self.model.clear()
        self.model.setHorizontalHeaderLabels(self.original_columns)
        start = self.current_page * self.page_size
        end = min(start + self.page_size, len(self.current_data))
        page_rows = self.current_data[start:end]

        for row_data in page_rows:
            items = [QStandardItem(str(field)) for field in row_data]
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

    def open_filter_dialog(self):
        if not self.original_columns:
            return
        dlg = FilterDialog(self.original_columns, self, self.current_filter_root)
        dlg.filterApplied.connect(self.apply_filter)
        dlg.exec()

    def apply_filter(self, root_node):
        """应用筛选：保存状态，过滤数据，刷新表格。"""
        self.current_filter_root = root_node
        start = time.time()
        try:
            filtered_rows = [row for row in self.original_rows if self._eval_node(root_node, row)]
            elapsed = (time.time() - start) * 1000
            self.current_data = filtered_rows
            self.current_page = 0
            self._show_current_page()
            self._update_stats(len(self.original_rows), len(filtered_rows), elapsed)
            self._update_pagination_state()
        except Exception as e:
            QMessageBox.warning(self, "筛选错误", str(e))

    def _eval_node(self, node, row):
        """递归判断行是否满足筛选节点。"""
        if isinstance(node, FilterConditionNode):
            return self._eval_condition(node, row)
        elif isinstance(node, FilterGroupNode):
            if not node.enabled or not node.children:
                return True
            results = [self._eval_node(child, row) for child in node.children]
            # 应用连接符
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
        """判断单行是否满足条件。"""
        if not cond.enabled:
            return True
        col_idx = self.original_columns.index(cond.column) if cond.column in self.original_columns else -1
        if col_idx == -1:
            return True
        cell = row[col_idx]
        op = cond.operator
        val = cond.value

        # 处理 NULL
        if op == "is_null":
            return cell is None or str(cell).strip() == ""
        if op == "is_not_null":
            return cell is not None and str(cell).strip() != ""

        # 转换为字符串进行比较
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
