# ui_manager.py

import os
import time
from PySide6.QtWidgets import (
    QTableView, QWidget, QScrollBar, QStyleOptionSlider, QStyle,
    QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea, QLabel, QFrame,
    QDialog, QComboBox, QLineEdit, QDialogButtonBox, QToolButton,
    QSpinBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QStandardItemModel, QStandardItem, QIntValidator


# -------------------- 游标覆盖层 --------------------
class CursorOverlay(QWidget):
    """半透明游标覆盖层，跟随当前行移动。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(50, 150, 255, 80);")
        self.hide()


# -------------------- 表格视图 --------------------
class TableView(QTableView):
    """表格视图，游标行独立控制，不使用原生垂直滚动条。
    通过滚轮或滑块切换当前行，并始终保持该行可见。
    """
    cursor_row_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollMode(QTableView.ScrollPerItem)
        self.setSelectionMode(QTableView.NoSelection)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cursor_overlay = CursorOverlay(self.viewport())
        self.current_cursor_row = 0

    def wheelEvent(self, event):
        model = self.model()
        if not model or model.rowCount() == 0:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return
        step = -1 if delta > 0 else 1
        next_row = self.current_cursor_row + step
        if 0 <= next_row < model.rowCount():
            self.current_cursor_row = next_row
            self.scrollTo(model.index(next_row, 0), QTableView.EnsureVisible)
            self.update_cursor_position()
            self.cursor_row_changed.emit(next_row)
        event.accept()

    def set_cursor_row(self, row):
        """由外部滑块调用，跳转到指定行并更新覆盖层。"""
        model = self.model()
        if not model or row < 0 or row >= model.rowCount():
            return
        self.current_cursor_row = row
        self.scrollTo(model.index(row, 0), QTableView.EnsureVisible)
        self.update_cursor_position()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_cursor_position()

    def update_cursor_position(self):
        """根据当前游标行更新覆盖层的位置和大小。"""
        model = self.model()
        if not model or model.rowCount() == 0:
            self.cursor_overlay.hide()
            return
        rect = self.visualRect(model.index(self.current_cursor_row, 0))
        if rect.isValid():
            viewport_width = self.viewport().width()
            self.cursor_overlay.setGeometry(0, rect.y(), viewport_width, rect.height())
            self.cursor_overlay.show()
        else:
            self.cursor_overlay.hide()

    def reset_cursor(self):
        """加载新数据后重置游标到第一行。"""
        model = self.model()
        if not model or model.rowCount() == 0:
            self.cursor_overlay.hide()
            return
        self.current_cursor_row = 0
        self.scrollTo(model.index(0, 0), QTableView.EnsureVisible)
        self.update_cursor_position()
        self.cursor_row_changed.emit(0)


# -------------------- 自定义滑块 --------------------
class RowSlider(QScrollBar):
    """自定义垂直滚动条，拖拽时不会发生瞬移，且移动过程中不会丢失控制。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_offset = 0

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            slider_length = self.style().pixelMetric(QStyle.PM_SliderLength, opt, self)
            bar_length = self.rect().height()
            valid_length = bar_length - slider_length
            if valid_length > 0:
                slider_top = (self.value() - self.minimum()) / (self.maximum() - self.minimum()) * valid_length
                mouse_y = event.position().y()
                self._drag_offset = mouse_y - slider_top
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        slider_length = self.style().pixelMetric(QStyle.PM_SliderLength, opt, self)
        bar_length = self.rect().height()
        valid_length = bar_length - slider_length
        if valid_length > 0:
            slider_top = event.position().y() - self._drag_offset
            slider_top = max(0, min(slider_top, valid_length))
            new_value = self.minimum() + (slider_top / valid_length) * (self.maximum() - self.minimum())
            self.setValue(int(new_value))
            event.accept()
            return
        super().mouseMoveEvent(event)


# -------------------- 首页 --------------------
class HomePage(QWidget):
    """首页：数据表管理页。显示导入按钮和历史文件列表。"""

    import_requested = Signal()
    file_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("📂 数据表管理")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.btn_import = QPushButton("📁 导入新数据")
        self.btn_import.setFont(QFont("Arial", 12))
        self.btn_import.clicked.connect(self.import_requested.emit)
        layout.addWidget(self.btn_import)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        self.history_label = QLabel("📋 历史文件")
        self.history_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(self.history_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area)

        self.placeholder_label = QLabel("暂无导入记录")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: gray; font-size: 14px;")

    def set_file_list(self, paths):
        for i in reversed(range(self.scroll_layout.count())):
            widget = self.scroll_layout.itemAt(i).widget()
            if widget:
                self.scroll_layout.removeWidget(widget)
                widget.setParent(None)

        if not paths:
            self.scroll_layout.addWidget(self.placeholder_label)
            return

        for path in paths:
            name = os.path.basename(path)
            btn = QPushButton(f"{name}\n{path}")
            btn.setFlat(True)
            btn.setStyleSheet(
                "QPushButton { text-align: left; padding: 8px; border: 1px solid #ccc; border-radius: 4px; background: #f9f9f9; }"
                "QPushButton:hover { background: #e0f0ff; }"
            )
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(50)
            btn.clicked.connect(lambda checked=False, p=path: self.file_selected.emit(p))
            self.scroll_layout.addWidget(btn)


# -------------------- 高级筛选对话框 --------------------
class FilterDialog(QDialog):
    filterApplied = Signal(list, list)  # 条件列表, 逻辑连接词列表

    OPERATORS = {
        "等于": "==",
        "不等于": "!=",
        "大于": ">",
        "小于": "<",
        "大于等于": ">=",
        "小于等于": "<=",
        "包含(忽略大小写)": "icontains",
        "包含(区分大小写)": "contains",
        "不包含": "not_contains",
        "为空": "is_null",
        "不为空": "is_not_null",
    }

    def __init__(self, columns, parent=None):
        super().__init__(parent)
        self.columns = columns
        self.setWindowTitle("高级筛选")
        self.setMinimumWidth(600)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.condition_widget = QWidget()
        self.condition_layout = QVBoxLayout(self.condition_widget)
        self.condition_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.condition_widget)
        layout.addWidget(scroll)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("＋ 添加条件")
        self.add_btn.clicked.connect(self.add_condition)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addStretch()
        self.btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btn_box.button(QDialogButtonBox.Ok).setText("应用筛选")
        self.btn_box.button(QDialogButtonBox.Cancel).setText("取消")
        self.btn_box.accepted.connect(self.apply_filter)
        self.btn_box.rejected.connect(self.reject)
        btn_layout.addWidget(self.btn_box)
        layout.addLayout(btn_layout)

        self.conditions = []
        self.add_condition()

    def add_condition(self, logic="AND"):
        row = QHBoxLayout()

        logic_combo = QComboBox()
        logic_combo.addItems(["AND", "OR"])
        logic_combo.setCurrentText(logic)
        logic_combo.setFixedWidth(70)
        row.addWidget(logic_combo)

        col_combo = QComboBox()
        col_combo.addItems(self.columns)
        col_combo.setMinimumWidth(120)
        row.addWidget(col_combo)

        op_combo = QComboBox()
        op_combo.addItems(list(self.OPERATORS.keys()))
        op_combo.setMinimumWidth(140)
        row.addWidget(op_combo)

        value_edit = QLineEdit()
        value_edit.setPlaceholderText("筛选值")
        row.addWidget(value_edit)

        del_btn = QToolButton()
        del_btn.setText("✕")
        del_btn.setToolTip("移除此条件")
        del_btn.clicked.connect(lambda: self.remove_condition(row))
        row.addWidget(del_btn)

        def toggle_value_edit(op_text):
            if op_text in ("为空", "不为空"):
                value_edit.setEnabled(False)
                value_edit.clear()
            else:
                value_edit.setEnabled(True)

        op_combo.currentTextChanged.connect(toggle_value_edit)

        self.condition_layout.addLayout(row)
        self.conditions.append(row)

        if len(self.conditions) == 1:
            logic_combo.hide()

    def remove_condition(self, row_layout):
        while row_layout.count():
            item = row_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
            elif item.layout():
                self._clear_item_layout(item.layout())
        self.condition_layout.removeItem(row_layout)
        self.conditions.remove(row_layout)
        for i, cond in enumerate(self.conditions):
            logic_combo = cond.itemAt(0).widget()
            if isinstance(logic_combo, QComboBox):
                logic_combo.setVisible(i != 0)

    def _clear_item_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
            elif item.layout():
                self._clear_item_layout(item.layout())

    def apply_filter(self):
        cond_list = []
        logic_list = []
        for i, row in enumerate(self.conditions):
            logic_combo = row.itemAt(0).widget()
            col_combo = row.itemAt(1).widget()
            op_combo = row.itemAt(2).widget()
            value_edit = row.itemAt(3).widget()

            column = col_combo.currentText()
            op_display = op_combo.currentText()
            value = value_edit.text().strip() if value_edit.isEnabled() else None

            if op_display not in ("为空", "不为空") and not value:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "提示", "请为每个条件输入筛选值")
                return

            cond_list.append({
                "column": column,
                "operator": self.OPERATORS[op_display],
                "value": value
            })
            logic_list.append(logic_combo.currentText() if i > 0 else "AND")

        self.filterApplied.emit(cond_list, logic_list)
        self.accept()


# -------------------- 数据浏览页（含分页） --------------------
class DataViewPage(QWidget):
    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_columns = []
        self.original_rows = []  # 全量原始数据
        self.current_data = []  # 当前筛选后的全部数据
        self.page_size = 1000
        self.current_page = 0  # 0-based
        self.query_elapsed_ms = 0
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # ---------- 顶部导航栏 ----------
        top_bar = QHBoxLayout()
        self.btn_back = QPushButton("← 返回首页")
        self.btn_back.clicked.connect(self.back_requested.emit)
        top_bar.addWidget(self.btn_back)

        self.current_file_label = QLabel("")
        self.current_file_label.setFont(QFont("Arial", 10))
        top_bar.addWidget(self.current_file_label)

        # 统计信息
        self.stats_label = QLabel("")
        self.stats_label.setFont(QFont("Arial", 9))
        self.stats_label.setStyleSheet("color: #666; margin-left: 10px;")
        top_bar.addWidget(self.stats_label)

        top_bar.addStretch()

        self.filter_btn = QPushButton("🔍 高级筛选")
        self.filter_btn.setToolTip("打开高级筛选对话框")
        self.filter_btn.clicked.connect(self.open_filter_dialog)
        top_bar.addWidget(self.filter_btn)

        layout.addLayout(top_bar)

        # ---------- 表格与滑块 ----------
        h_layout = QHBoxLayout()
        self.table_view = TableView()
        self.row_slider = RowSlider()
        self.row_slider.setOrientation(Qt.Vertical)
        self.row_slider.setRange(0, 0)
        h_layout.addWidget(self.table_view)
        h_layout.addWidget(self.row_slider)
        layout.addLayout(h_layout)

        # ---------- 分页控件 ----------
        pagination_layout = QHBoxLayout()
        self.btn_first = QPushButton("第一页")
        self.btn_first.setToolTip("转到第一页")
        self.btn_prev = QPushButton("上一页")
        self.btn_prev.setToolTip("转到上一页")

        self.page_input = QLineEdit()
        self.page_input.setFixedWidth(60)
        self.page_input.setAlignment(Qt.AlignCenter)
        self.page_input.setValidator(QIntValidator(1, 999999, self))
        self.page_input.setToolTip("输入页码按回车跳转")

        self.btn_next = QPushButton("下一页")
        self.btn_next.setToolTip("转到下一页")
        self.btn_last = QPushButton("最后一页")
        self.btn_last.setToolTip("转到最后一页")

        self.page_info_label = QLabel("")
        self.page_info_label.setAlignment(Qt.AlignCenter)

        pagination_layout.addStretch()
        pagination_layout.addWidget(self.btn_first)
        pagination_layout.addWidget(self.btn_prev)
        pagination_layout.addWidget(QLabel("页码："))
        pagination_layout.addWidget(self.page_input)
        pagination_layout.addWidget(self.btn_next)
        pagination_layout.addWidget(self.btn_last)
        pagination_layout.addSpacing(20)
        pagination_layout.addWidget(self.page_info_label)
        pagination_layout.addStretch()
        layout.addLayout(pagination_layout)

        # 信号连接
        self.btn_first.clicked.connect(self._first_page)
        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_next.clicked.connect(self._next_page)
        self.btn_last.clicked.connect(self._last_page)
        self.page_input.returnPressed.connect(self._input_page)

        self.table_view.cursor_row_changed.connect(self._on_cursor_row_changed)
        self.row_slider.valueChanged.connect(self._on_slider_value_changed)

        # 初始禁用分页控件
        self._update_pagination_state()

    def _on_cursor_row_changed(self, row):
        self.row_slider.blockSignals(True)
        self.row_slider.setValue(row)
        self.row_slider.blockSignals(False)

    def _on_slider_value_changed(self, row):
        self.table_view.set_cursor_row(row)

    # ---------- 数据加载 ----------
    def display_data(self, columns, rows, file_name, query_elapsed_ms):
        """接收全量数据，初始化分页并显示第一页。"""
        self.original_columns = columns
        self.original_rows = rows
        self.current_data = rows
        self.query_elapsed_ms = query_elapsed_ms
        self.current_file_label.setText(f"当前文件：{file_name}")
        self.current_page = 0
        self._show_current_page()
        self._update_stats(len(rows), None, query_elapsed_ms)
        self._update_pagination_state()

    # ---------- 分页核心方法 ----------
    def _total_pages(self):
        if not self.current_data:
            return 0
        return max(1, (len(self.current_data) + self.page_size - 1) // self.page_size)

    def _show_current_page(self):
        """根据 current_page 和 current_data 更新表格模型。"""
        total = len(self.current_data)
        if total == 0:
            self._update_model([])
            return

        start = self.current_page * self.page_size
        end = min(start + self.page_size, total)
        page_rows = self.current_data[start:end]
        self._update_model(page_rows)
        self.page_info_label.setText(f"第 {self.current_page + 1} 页 / 共 {self._total_pages()} 页")

    def _update_model(self, rows):
        """用给定的行数据刷新表格和滑块范围。"""
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(self.original_columns)
        for row in rows:
            row_str = [str(item) if item is not None else "" for item in row]
            model.appendRow([QStandardItem(v) for v in row_str])
        self.table_view.setModel(model)
        max_row = max(0, len(rows) - 1)
        self.row_slider.setRange(0, max_row)
        self.table_view.reset_cursor()

    def _update_pagination_state(self):
        """根据当前页和总页数更新按钮和输入框状态。"""
        total = self._total_pages()
        self.btn_first.setEnabled(total > 1 and self.current_page > 0)
        self.btn_prev.setEnabled(self.current_page > 0)
        self.btn_next.setEnabled(self.current_page < total - 1)
        self.btn_last.setEnabled(total > 1 and self.current_page < total - 1)
        self.page_input.setEnabled(total > 1)
        if total > 0:
            self.page_input.setText(str(self.current_page + 1))

    # ---------- 翻页动作 ----------
    def _go_to_page(self, page_num):
        """跳转到指定页码（0-based）。"""
        total = self._total_pages()
        if total == 0:
            return
        page_num = max(0, min(page_num, total - 1))
        if page_num == self.current_page:
            return
        self.current_page = page_num
        self._show_current_page()
        self._update_pagination_state()

    def _first_page(self):
        self._go_to_page(0)

    def _prev_page(self):
        self._go_to_page(self.current_page - 1)

    def _next_page(self):
        self._go_to_page(self.current_page + 1)

    def _last_page(self):
        self._go_to_page(self._total_pages() - 1)

    def _input_page(self):
        """处理手动输入页码跳转。"""
        text = self.page_input.text().strip()
        if not text:
            return
        try:
            page_num = int(text) - 1  # 转为 0-based
            self._go_to_page(page_num)
        except ValueError:
            pass
        finally:
            # 恢复输入框显示当前页码
            self.page_input.setText(str(self.current_page + 1))

    # ---------- 统计信息 ----------
    def _update_stats(self, total, filtered=None, elapsed_ms=None):
        txt = f"总行数：{total}"
        if filtered is not None:
            txt += f" | 筛选后：{filtered}"
        if elapsed_ms is not None:
            txt += f" | 耗时：{elapsed_ms:.2f} ms"
        self.stats_label.setText(txt)

    # ---------- 高级筛选 ----------
    def open_filter_dialog(self):
        if not self.original_columns:
            return
        dlg = FilterDialog(self.original_columns, self)
        dlg.filterApplied.connect(self.apply_filter)
        dlg.exec()

    def apply_filter(self, cond_list, logic_list):
        start = time.time()
        try:
            filtered_rows = [row for row in self.original_rows if self._check_row(row, cond_list, logic_list)]
            elapsed = (time.time() - start) * 1000
            # 更新筛选后的完整数据
            self.current_data = filtered_rows
            self.current_page = 0
            self._show_current_page()
            self._update_stats(len(self.original_rows), len(filtered_rows), elapsed)
            self._update_pagination_state()
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "筛选错误", str(e))

    def _check_row(self, row, cond_list, logic_list):
        if not cond_list:
            return True
        result = self._eval_condition(row, cond_list[0])
        for i in range(1, len(cond_list)):
            cond_result = self._eval_condition(row, cond_list[i])
            logic = logic_list[i]
            if logic == "AND":
                result = result and cond_result
            else:
                result = result or cond_result
        return result

    def _eval_condition(self, row, cond):
        col_name = cond["column"]
        op = cond["operator"]
        value = cond["value"]

        try:
            col_idx = self.original_columns.index(col_name)
        except ValueError:
            return False

        if col_idx >= len(row):
            return False
        cell_value = row[col_idx]

        if cell_value is None:
            if op == "is_null":
                return True
            elif op == "is_not_null":
                return False
            else:
                return False

        cell_str = str(cell_value)

        if op in ("==", "!=", ">", "<", ">=", "<="):
            try:
                cell_num = float(cell_value)
                val_num = float(value)
                if op == "==":
                    return cell_num == val_num
                elif op == "!=":
                    return cell_num != val_num
                elif op == ">":
                    return cell_num > val_num
                elif op == "<":
                    return cell_num < val_num
                elif op == ">=":
                    return cell_num >= val_num
                elif op == "<=":
                    return cell_num <= val_num
            except ValueError:
                if op == "==":
                    return cell_str == value
                elif op == "!=":
                    return cell_str != value
                else:
                    return False
        elif op == "icontains":
            return value.lower() in cell_str.lower()
        elif op == "contains":
            return value in cell_str
        elif op == "not_contains":
            return value not in cell_str
        elif op == "is_null":
            return cell_value is None
        elif op == "is_not_null":
            return cell_value is not None
        else:
            return False
