# ui_manager.py

from PySide6.QtWidgets import QTableView
from PySide6.QtWidgets import (QScrollBar, QStyleOptionSlider, QStyle)
from PySide6.QtCore import Qt


class TableView(QTableView):
    """自定义表格视图，彻底锁定滚轮单次只滚动 1 行"""

    def wheelEvent(self, event):
        # 获取滚轮滚动的角度变化
        delta = event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return

        # 获取垂直滚动条
        v_scrollbar = self.verticalScrollBar()

        # delta > 0 代表向上滚动，滚动条值减少；delta < 0 代表向下滚动，滚动条值增加
        if delta > 0:
            v_scrollbar.setValue(v_scrollbar.value() - 1)
        else:
            v_scrollbar.setValue(v_scrollbar.value() + 1)

        # 接受并消耗掉该事件，阻止它继续向上传递导致滚动 3 行
        event.accept()


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
