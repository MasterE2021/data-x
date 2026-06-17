# file_name: ui_home.py
import sys
from PySide6 import QtWidgets, QtCore, QtGui

str_min = "−"
str_window = "❒"
str_max = "☐"
str_close = "×"
str_setting = "设置"

BORDER_WIDTH = 6


class CustomTitleBar(QtWidgets.QWidget):
    """自定义标题栏，左侧标题，右侧功能键"""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(38)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(0)

        self.title_label = QtWidgets.QLabel("Fast Data")
        self.title_label.setStyleSheet("color: #333; font-size: 14px; font-weight: 500;")
        layout.addWidget(self.title_label)

        layout.addStretch()

        self.btn_settings = QtWidgets.QPushButton(str_setting)
        self.btn_min = QtWidgets.QPushButton(str_min)
        self.btn_max = QtWidgets.QPushButton(str_max)
        self.btn_close = QtWidgets.QPushButton(str_close)

        btn_style = """
            QPushButton {
                border: none;
                background: transparent;
                padding: 0;
                margin: 0;
                font-size: 14px;
                min-width: 40px;
                min-height: 38px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """
        close_style = btn_style + """
            QPushButton:hover {
                background-color: #e81123;
                color: white;
            }
        """
        self.btn_settings.setStyleSheet(btn_style)
        self.btn_min.setStyleSheet(btn_style)
        self.btn_max.setStyleSheet(btn_style)
        self.btn_close.setStyleSheet(close_style)

        layout.addWidget(self.btn_settings)
        layout.addSpacing(8)
        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)

        self.btn_min.clicked.connect(parent.showMinimized)
        self.btn_max.clicked.connect(self.toggle_maximize)
        self.btn_close.clicked.connect(parent.close)

        self.maximized = False
        self.drag_pos = None
        self.setMouseTracking(True)

    def toggle_maximize(self):
        if self.maximized:
            self.parent.showNormal()
            self.maximized = False
            self.btn_max.setText(str_max)
        else:
            self.parent.showMaximized()
            self.maximized = True
            self.btn_max.setText(str_window)

    def _get_edges(self, pos):
        edges = QtCore.Qt.Edge(0)
        x, y = pos.x(), pos.y()
        w = self.width()
        if y <= BORDER_WIDTH:
            edges |= QtCore.Qt.Edge.TopEdge
        if x <= BORDER_WIDTH:
            edges |= QtCore.Qt.Edge.LeftEdge
        if x >= w - BORDER_WIDTH:
            edges |= QtCore.Qt.Edge.RightEdge
        return edges

    def _update_cursor(self, pos):
        edges = self._get_edges(pos)
        on_left = edges & QtCore.Qt.Edge.LeftEdge
        on_right = edges & QtCore.Qt.Edge.RightEdge
        on_top = edges & QtCore.Qt.Edge.TopEdge

        if (on_left and on_top) or (on_right and on_top):
            cursor = QtCore.Qt.CursorShape.SizeFDiagCursor if (
                    on_left and on_top) else QtCore.Qt.CursorShape.SizeBDiagCursor
        elif on_left or on_right:
            cursor = QtCore.Qt.CursorShape.SizeHorCursor
        elif on_top:
            cursor = QtCore.Qt.CursorShape.SizeVerCursor
        else:
            cursor = QtCore.Qt.CursorShape.ArrowCursor
        self.setCursor(cursor)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            edges = self._get_edges(pos)
            if edges != QtCore.Qt.Edge(0):
                self.parent.windowHandle().startSystemResize(edges)
                self.drag_pos = None
            else:
                self.drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.drag_pos is not None:
            delta = event.globalPosition().toPoint() - self.drag_pos
            self.parent.move(self.parent.pos() + delta)
            self.drag_pos = event.globalPosition().toPoint()
        else:
            self._update_cursor(event.position().toPoint())

    def mouseReleaseEvent(self, event):
        self.drag_pos = None

    def mouseDoubleClickEvent(self, event):
        """双击标题栏空白区域：最大化/窗口化切换"""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            # 判断是否点在按钮上，避免按钮双击触发窗口切换
            pos = event.position().toPoint()
            child = self.childAt(pos)
            if child is None or child is self.title_label:
                self.toggle_maximize()
        super().mouseDoubleClickEvent(event)


class MainWindow(QtWidgets.QWidget):
    """无边框主窗口，四周边缘可调整大小"""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
        self.resize(800, 600)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.title_bar = CustomTitleBar(self)
        main_layout.addWidget(self.title_bar)

        # 内容区域（用普通 QWidget 并打开鼠标追踪）
        self.content = QtWidgets.QWidget()
        self.content.setStyleSheet("background-color: #f5f5f5;")
        self.content.setMouseTracking(True)  # 关键：允许鼠标移动通知
        main_layout.addWidget(self.content)

        # 内容区里的一个标签
        label = QtWidgets.QLabel("主内容区域", alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 16px;")
        content_layout = QtWidgets.QVBoxLayout(self.content)
        content_layout.addWidget(label)

        self.setStyleSheet("""
            MainWindow {
                background: white;
                border: 1px solid #ccc;
            }
        """)

        self.setMouseTracking(True)

        # 安装事件过滤器，接管子控件的鼠标事件
        self.content.installEventFilter(self)

    def eventFilter(self, obj, event):
        """过滤子控件（content）的鼠标事件，转为窗口级别的边缘检测"""
        if obj is self.content:
            if event.type() == QtCore.QEvent.Type.MouseMove:
                # 将子控件内的坐标转换为 MainWindow 坐标
                local_pos = self.content.mapTo(self, event.position().toPoint())
                self._update_cursor_from_pos(local_pos)
            elif event.type() == QtCore.QEvent.Type.MouseButtonPress:
                if event.button() == QtCore.Qt.MouseButton.LeftButton:
                    local_pos = self.content.mapTo(self, event.position().toPoint())
                    self._start_resize_from_pos(local_pos)
                    return True  # 吃掉事件，避免继续传递造成奇怪行为
        return super().eventFilter(obj, event)

    def _update_cursor_from_pos(self, pos):
        """根据主窗口坐标更新光标"""
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        on_left = x <= BORDER_WIDTH
        on_right = x >= w - BORDER_WIDTH
        on_top = y <= BORDER_WIDTH
        on_bottom = y >= h - BORDER_WIDTH

        cursor = QtCore.Qt.CursorShape.ArrowCursor
        if (on_left and on_top) or (on_right and on_bottom):
            cursor = QtCore.Qt.CursorShape.SizeFDiagCursor
        elif (on_left and on_bottom) or (on_right and on_top):
            cursor = QtCore.Qt.CursorShape.SizeBDiagCursor
        elif on_left or on_right:
            cursor = QtCore.Qt.CursorShape.SizeHorCursor
        elif on_top or on_bottom:
            cursor = QtCore.Qt.CursorShape.SizeVerCursor
        self.setCursor(cursor)

    def _start_resize_from_pos(self, pos):
        """根据主窗口坐标开始系统级窗口调整"""
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        edges = QtCore.Qt.Edge(0)

        if x <= BORDER_WIDTH:
            edges |= QtCore.Qt.Edge.LeftEdge
        elif x >= w - BORDER_WIDTH:
            edges |= QtCore.Qt.Edge.RightEdge
        if y <= BORDER_WIDTH:
            edges |= QtCore.Qt.Edge.TopEdge
        elif y >= h - BORDER_WIDTH:
            edges |= QtCore.Qt.Edge.BottomEdge

        if edges != QtCore.Qt.Edge(0):
            self.windowHandle().startSystemResize(edges)

    # 兼容直接在主窗口空白处的鼠标事件（很少用到，但保留无妨）
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._start_resize_from_pos(event.position().toPoint())

    def mouseMoveEvent(self, event):
        self._update_cursor_from_pos(event.position().toPoint())


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
