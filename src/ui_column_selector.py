# ui_column_selector.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QDialogButtonBox
)
from PySide6.QtCore import Qt


class ColumnSelectorDialog(QDialog):
    """选择需要显示/导出的列"""

    def __init__(self, all_columns, checked_indices, parent=None):
        super().__init__(parent)
        self.all_columns = all_columns
        self.checked_indices = set(checked_indices)
        self.setWindowTitle("选择可见列")
        self.setup_ui()
        self.update_button_states()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 全选/取消全选按钮
        btn_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.clicked.connect(self.select_all)
        self.btn_deselect_all = QPushButton("取消全选")
        self.btn_deselect_all.clicked.connect(self.deselect_all)
        btn_layout.addWidget(self.btn_select_all)
        btn_layout.addWidget(self.btn_deselect_all)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 列列表（可勾选）
        self.list_widget = QListWidget()
        for i, col in enumerate(self.all_columns):
            item = QListWidgetItem(col)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if i in self.checked_indices else Qt.Unchecked)
            self.list_widget.addItem(item)
        self.list_widget.itemChanged.connect(self.on_item_changed)
        layout.addWidget(self.list_widget)

        # 确认/取消按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def select_all(self):
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(Qt.Checked)
        self.update_button_states()

    def deselect_all(self):
        # 至少保留一列（第一列）
        for i in range(self.list_widget.count()):
            if i == 0:
                self.list_widget.item(i).setCheckState(Qt.Checked)
            else:
                self.list_widget.item(i).setCheckState(Qt.Unchecked)
        self.update_button_states()

    def on_item_changed(self, item):
        # 确保至少有一列被选中
        if item.checkState() == Qt.Unchecked:
            if all(self.list_widget.item(i).checkState() == Qt.Unchecked
                   for i in range(self.list_widget.count())):
                item.setCheckState(Qt.Checked)
        self.update_button_states()

    def update_button_states(self):
        all_checked = all(self.list_widget.item(i).checkState() == Qt.Checked
                          for i in range(self.list_widget.count()))
        self.btn_select_all.setEnabled(not all_checked)
        self.btn_deselect_all.setEnabled(True)

    def get_selected_indices(self):
        return [i for i in range(self.list_widget.count())
                if self.list_widget.item(i).checkState() == Qt.Checked]
