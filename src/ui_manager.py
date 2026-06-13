# ui_manager.py

from PySide6.QtWidgets import QTableView, QWidget, QScrollBar, QStyleOptionSlider, QStyle
from PySide6.QtCore import Qt


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
    """自定义表格视图，彻底锁定滚轮单次只滚动 1 行"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # 强制按行(Item)滚动，以保障游标对齐绝对准确
        self.setVerticalScrollMode(QTableView.ScrollPerItem)
        self.setSelectionMode(QTableView.NoSelection)

        # 初始化独立游标行组件，并将其父对象绑定为 viewport (使其只在数据视口内显示)
        self.cursor_overlay = CursorOverlay(self.viewport())

        # 核心状态位
        self.current_cursor_row = 0  # 游标行所在的绝对行索引
        self.relative_cursor_offset = 0  # 游标行距离视口顶部第一行的“相对行数”
        self._wheel_scrolling = False  # 状态锁：区分是滚轮触发的视口变动，还是滑块拖拽触发的变动

    def setVerticalScrollBar(self, scrollbar):
        # 覆写此方法：当外部注入自定义的 RowSlider 时，必须重新绑定信号以监听拖拽
        super().setVerticalScrollBar(scrollbar)
        self.verticalScrollBar().valueChanged.connect(self.on_scrollbar_value_changed)

    def wheelEvent(self, event):
        model = self.model()
        if not model or model.rowCount() == 0:
            return

        # 获取滚轮滚动的角度变化
        delta = event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return

        # 获取垂直滚动条
        v_scrollbar = self.verticalScrollBar()

        # delta > 0 代表向上滚动，滚动条值减少；delta < 0 代表向下滚动，滚动条值增加
        # （结合游标行逻辑：向上滚动游标行减少，向下滚动游标行增加）
        step = -1 if delta > 0 else 1
        next_row = self.current_cursor_row + step

        # 确保游标行不超过数据边界
        if 0 <= next_row < model.rowCount():
            self._wheel_scrolling = True
            self.current_cursor_row = next_row

            # EnsureVisible 判断：游标在视界内不滚动数据；脱离视界则只滚动刚好1行
            self.scrollTo(model.index(next_row, 0), QTableView.EnsureVisible)
            self.update_cursor_position()

            # 滚动完成后，更新游标所在位置相对于视口顶部的“偏移量”
            top_row = v_scrollbar.value()
            self.relative_cursor_offset = self.current_cursor_row - top_row
            self._wheel_scrolling = False

        # 接受并消耗掉该事件，阻止它继续向上传递导致滚动 3 行
        event.accept()

    def on_scrollbar_value_changed(self, value):
        """当滑块被拖拽时触发，保持游标的相对视界位置，并在触顶/底时吸附"""
        if self._wheel_scrolling:
            return  # 如果是由鼠标滚轮(被动)发起的滚动条变化，跳过该处理逻辑

        model = self.model()
        if not model or model.rowCount() == 0:
            return

        max_row = model.rowCount() - 1
        scrollbar = self.verticalScrollBar()

        # 【修复问题 1】：触顶/触底时的绝对吸附与相对位置重置
        if value == scrollbar.minimum():
            # 滑块置顶：游标强制归零，并重置相对偏移为 0（此后拖动将锁定在视口第一行）
            self.current_cursor_row = 0
            self.relative_cursor_offset = 0
        elif value == scrollbar.maximum():
            # 滑块触底：游标强制到达最后一行，并重置相对偏移（此后拖动将锁定在视口最后一行）
            self.current_cursor_row = max_row
            self.relative_cursor_offset = self.current_cursor_row - value
        else:
            # 正常拖动期间：严格保持之前的相对视口位置
            new_cursor_row = value + self.relative_cursor_offset
            self.current_cursor_row = max(0, min(new_cursor_row, max_row))

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
        self.relative_cursor_offset = 0
        self.verticalScrollBar().setValue(0)
        self.scrollTo(model.index(0, 0), QTableView.EnsureVisible)
        self.update_cursor_position()


class RowSlider(QScrollBar):
    """自定义垂直滚动条，只要鼠标左键不松，移动多远都不会丢失控制"""

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
            # 获取鼠标当前相对于滚动条顶部的 Y 坐标（并限制在滚动条范围内）
            mouse_y = max(0, min(event.position().y() - slider_length / 2, valid_length))

            # 计算对应的滚动条数值位置
            new_value = self.minimum() + (mouse_y / valid_length) * (self.maximum() - self.minimum())
            self.setValue(int(new_value))
            event.accept()
            return
