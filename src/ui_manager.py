# ui_manager.py

import os
from PySide6.QtWidgets import (
    QTableView, QWidget, QScrollBar, QStyleOptionSlider, QStyle,
    QVBoxLayout, QPushButton, QScrollArea, QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


# -------------------------- 游标覆盖层 --------------------------
class CursorOverlay(QWidget):
    """半透明游标覆盖层，跟随当前行移动。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(50, 150, 255, 80);")
        self.hide()


# -------------------------- 表格视图 --------------------------
class TableView(QTableView):
    """
    自定义表格视图。
    - 禁用垂直滚动条，使用游标行浏览。
    - 滚轮事件控制游标上下移动。
    - 发出 cursor_row_changed 信号。
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


# -------------------------- 自定义滑块 --------------------------
class RowSlider(QScrollBar):
    """
    右侧滑块，用于指示游标行位置，支持拖拽无瞬移。 点击滑块边缘时保持平滑移动。
    """

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
