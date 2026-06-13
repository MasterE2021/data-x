# ui_manager.py

from PySide6.QtWidgets import QTableView, QWidget, QScrollBar, QStyleOptionSlider, QStyle
from PySide6.QtCore import Qt, Signal


class CursorOverlay(QWidget):
    """独立的游标行透明色块（遮罩层）"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # 让鼠标事件穿透，不影响底层单元格的正常点击交互
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        # 强制让原生的 QWidget 支持并绘制背景色样式！
        self.setAttribute(Qt.WA_StyledBackground, True)

        # 设置半透明的背景色（例如：淡蓝色 80/255 透明度）
        self.setStyleSheet("background-color: rgba(50, 150, 255, 80);")
        self.hide()


class TableView(QTableView):
    """自定义表格视图，游标行独立控制，不依赖垂直滚动条"""

    # 信号：游标行发生变化（row 是新行号）
    cursor_row_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        # 强制按行(Item)滚动，以保障游标对齐绝对准确
        self.setVerticalScrollMode(QTableView.ScrollPerItem)
        self.setSelectionMode(QTableView.NoSelection)

        # 隐藏原生垂直滚动条，因为我们使用外部的游标滑块
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.cursor_overlay = CursorOverlay(self.viewport())
        self.current_cursor_row = 0

    def wheelEvent(self, event):
        model = self.model()
        if not model or model.rowCount() == 0:
            return

        # 获取滚轮滚动的角度变化
        delta = event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return

        # delta > 0 代表向上滚动，游标上移；delta < 0 代表向下滚动，游标下移
        step = -1 if delta > 0 else 1
        next_row = self.current_cursor_row + step

        # 确保游标行不超过数据边界
        if 0 <= next_row < model.rowCount():
            self.current_cursor_row = next_row

            # 确保游标行在视口中完全可见（若不可见则自动滚动视图）
            self.scrollTo(model.index(next_row, 0), QTableView.EnsureVisible)
            self.update_cursor_position()

            # 通知外部滑块更新位置
            self.cursor_row_changed.emit(next_row)

        # 接受并消耗掉该事件，阻止它继续向上传递导致滚动 3 行
        event.accept()

    def set_cursor_row(self, row):
        """由外部滑块调用，设置游标到指定行并滚动视图使其可见"""
        model = self.model()
        if not model or row < 0 or row >= model.rowCount():
            return
        self.current_cursor_row = row
        self.scrollTo(model.index(row, 0), QTableView.EnsureVisible)
        self.update_cursor_position()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 窗口大小发生改变时，同步更新游标色块的宽度
        self.update_cursor_position()

    def update_cursor_position(self):
        """核心渲染：物理更新游标层的位置和大小"""
        model = self.model()
        if not model or model.rowCount() == 0:
            self.cursor_overlay.hide()
            return

        # 获取目标行在视口中的物理位置信息
        rect = self.visualRect(model.index(self.current_cursor_row, 0))

        if rect.isValid():
            # 游标行可见时，覆盖整个视口的宽度
            viewport_width = self.viewport().width()
            self.cursor_overlay.setGeometry(0, rect.y(), viewport_width, rect.height())
            self.cursor_overlay.show()
        else:
            self.cursor_overlay.hide()

    def reset_cursor(self):
        """导入新数据后强制重置游标到第一行"""
        model = self.model()
        if not model or model.rowCount() == 0:
            self.cursor_overlay.hide()
            return
        self.current_cursor_row = 0
        self.scrollTo(model.index(0, 0), QTableView.EnsureVisible)
        self.update_cursor_position()
        self.cursor_row_changed.emit(0)


class RowSlider(QScrollBar):
    """自定义垂直滚动条，只要鼠标左键不松，移动多远都不会丢失控制，
    且拖拽起始不会因为点击位置而瞬移。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # 记录拖拽时鼠标相对于滑块顶部的偏移量
        self._drag_offset = 0

    def mousePressEvent(self, event):
        """按下鼠标时记录相对偏移，避免拖拽起始瞬移"""
        if event.button() == Qt.LeftButton:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)

            slider_length = self.style().pixelMetric(QStyle.PM_SliderLength, opt, self)
            bar_length = self.rect().height()
            valid_length = bar_length - slider_length

            if valid_length > 0:
                # 当前滑块顶部在滑动槽中的位置
                slider_top = (self.value() - self.minimum()) / (self.maximum() - self.minimum()) * valid_length
                # 鼠标在滚动条上的局部 y 坐标
                mouse_y = event.position().y()
                # 存储鼠标到滑块顶部的垂直距离
                self._drag_offset = mouse_y - slider_top
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # 其他情况（如未按左键或普通滑过）交由父类处理
        if not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return

        # 只有在鼠标左键按住拖拽时才进行强制拦截
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)

        # 获取滚动条滑块的有效滑动槽长度（总长度减去滑块自身长度）
        slider_length = self.style().pixelMetric(QStyle.PM_SliderLength, opt, self)
        bar_length = self.rect().height()
        valid_length = bar_length - slider_length

        if valid_length > 0:
            # 根据鼠标当前位置和初始偏移，反算滑块顶部应处的位置
            slider_top = event.position().y() - self._drag_offset
            # 限制滑块顶部在有效范围内
            slider_top = max(0, min(slider_top, valid_length))

            # 计算对应的滑块数值
            new_value = self.minimum() + (slider_top / valid_length) * (self.maximum() - self.minimum())
            self.setValue(int(new_value))
            event.accept()
            return

        super().mouseMoveEvent(event)
