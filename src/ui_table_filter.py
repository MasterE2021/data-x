# ui_table_filter.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLineEdit,
    QDialog, QDialogButtonBox, QToolButton, QCheckBox, QLabel,
    QScrollArea, QTextEdit, QPushButton
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


# -------------------------- 筛选节点数据结构 --------------------------
class FilterConditionNode:
    """叶子节点：一个具体的比较条件。"""

    def __init__(self, column, operator, value, enabled=True):
        self.column = column
        self.operator = operator  # 如 "==", "contains", "is_null" 等
        self.value = value
        self.enabled = enabled


class FilterGroupNode:
    """分组节点：包含多个子节点（条件/组）及它们之间的连接词。"""

    def __init__(self, children=None, connectors=None, enabled=True):
        self.children = children if children else []
        self.connectors = connectors if connectors else []  # 长度应为 len(children)-1
        self.enabled = enabled


# -------------------------- 条件控件（叶子） --------------------------
class ConditionWidget(QWidget):
    """单个筛选条件的交互组件。"""
    removed = Signal(QWidget)
    add_sibling_condition = Signal()
    add_sibling_group = Signal()
    connector_changed = Signal()

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

    def __init__(self, columns, indent_level=0, connector="AND", parent=None):
        super().__init__(parent)
        self.columns = columns
        self.indent_level = indent_level
        self._is_last = False
        self._connector = connector
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        # 缩进占位（嵌套层级）
        indent_spacer = QWidget()
        indent_spacer.setFixedWidth(self.indent_level * 20)
        layout.addWidget(indent_spacer)

        # 启用复选框
        self.enabled_check = QCheckBox()
        self.enabled_check.setChecked(True)
        self.enabled_check.toggled.connect(lambda: self.connector_changed.emit())
        layout.addWidget(self.enabled_check)

        # 列选择下拉
        self.col_combo = QComboBox()
        self.col_combo.addItems(self.columns)
        self.col_combo.setMinimumWidth(100)
        self.col_combo.currentTextChanged.connect(lambda: self.connector_changed.emit())
        layout.addWidget(self.col_combo)

        # 操作符下拉
        self.op_combo = QComboBox()
        self.op_combo.addItems(list(self.OPERATORS.keys()))
        self.op_combo.setMinimumWidth(130)
        self.op_combo.currentTextChanged.connect(self._on_operator_changed)
        self.op_combo.currentTextChanged.connect(lambda: self.connector_changed.emit())
        layout.addWidget(self.op_combo)

        # 值输入
        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText("筛选值")
        self.value_edit.textChanged.connect(lambda: self.connector_changed.emit())
        layout.addWidget(self.value_edit)

        # 逻辑连接词（AND/OR）
        self.connector_combo = QComboBox()
        self.connector_combo.addItems(["AND", "OR"])
        self.connector_combo.setCurrentText(self._connector)
        self.connector_combo.setFixedWidth(70)
        self.connector_combo.currentTextChanged.connect(lambda: self.connector_changed.emit())
        layout.addWidget(self.connector_combo)

        # 操作按钮
        del_btn = QToolButton()
        del_btn.setText("✕")
        del_btn.setToolTip("删除此条件")
        del_btn.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(del_btn)

        add_cond_btn = QToolButton()
        add_cond_btn.setText("＋条")
        add_cond_btn.setToolTip("在后面添加条件")
        add_cond_btn.clicked.connect(self.add_sibling_condition.emit)
        layout.addWidget(add_cond_btn)

        add_group_btn = QToolButton()
        add_group_btn.setText("＋组")
        add_group_btn.setToolTip("在后面添加条件组")
        add_group_btn.clicked.connect(self.add_sibling_group.emit)
        layout.addWidget(add_group_btn)

    def _on_operator_changed(self, op_text):
        """当操作符为'为空'或'不为空'时，禁用值输入框。"""
        self.value_edit.setEnabled(op_text not in ("为空", "不为空"))
        if not self.value_edit.isEnabled():
            self.value_edit.clear()

    def set_last(self, is_last):
        """控制连接词下拉的可见性（最后一个节点隐藏）。"""
        self._is_last = is_last
        self.connector_combo.setVisible(not is_last)

    def get_node(self):
        """返回该控件对应的 FilterConditionNode 对象。"""
        return FilterConditionNode(
            column=self.col_combo.currentText(),
            operator=self.OPERATORS[self.op_combo.currentText()],
            value=self.value_edit.text().strip() if self.value_edit.isEnabled() else None,
            enabled=self.enabled_check.isChecked()
        )

    def get_connector(self):
        return self.connector_combo.currentText()


# -------------------------- 条件组控件（括号容器） --------------------------
class GroupWidget(QWidget):
    """分组容器，内部包含子节点列表，并提供添加子节点按钮。"""
    removed = Signal(QWidget)
    add_sibling_condition = Signal()
    add_sibling_group = Signal()
    connector_changed = Signal()

    def __init__(self, columns, indent_level=0, connector="AND", parent=None):
        super().__init__(parent)
        self.columns = columns
        self.indent_level = indent_level
        self._connector = connector
        self._is_last = False
        self.child_widgets = []  # 子节点列表
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 2, 0, 2)
        main_layout.setSpacing(0)

        # 组头部行（含连接词、删除、添加兄弟按钮）
        header_row = QHBoxLayout()
        indent_spacer = QWidget()
        indent_spacer.setFixedWidth(self.indent_level * 20)
        header_row.addWidget(indent_spacer)

        self.enabled_check = QCheckBox()
        self.enabled_check.setChecked(True)
        self.enabled_check.toggled.connect(lambda: self.connector_changed.emit())
        header_row.addWidget(self.enabled_check)

        self.connector_combo = QComboBox()
        self.connector_combo.addItems(["AND", "OR"])
        self.connector_combo.setCurrentText(self._connector)
        self.connector_combo.setFixedWidth(70)
        self.connector_combo.currentTextChanged.connect(lambda: self.connector_changed.emit())
        header_row.addWidget(self.connector_combo)

        header_row.addStretch()

        del_btn = QToolButton()
        del_btn.setText("✕")
        del_btn.setToolTip("删除整个组")
        del_btn.clicked.connect(lambda: self.removed.emit(self))
        header_row.addWidget(del_btn)

        add_cond_btn = QToolButton()
        add_cond_btn.setText("＋条")
        add_cond_btn.setToolTip("在后面添加条件")
        add_cond_btn.clicked.connect(self.add_sibling_condition.emit)
        header_row.addWidget(add_cond_btn)

        add_group_btn = QToolButton()
        add_group_btn.setText("＋组")
        add_group_btn.setToolTip("在后面添加条件组")
        add_group_btn.clicked.connect(self.add_sibling_group.emit)
        header_row.addWidget(add_group_btn)

        main_layout.addLayout(header_row)

        # 子节点容器
        self.children_layout = QVBoxLayout()
        self.children_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addLayout(self.children_layout)

        # 左括号行
        left_bracket_row = QHBoxLayout()
        indent2 = QWidget()
        indent2.setFixedWidth((self.indent_level + 1) * 20)
        left_bracket_row.addWidget(indent2)
        left_bracket_row.addWidget(QLabel("("))
        left_bracket_row.addStretch()
        self.children_layout.addLayout(left_bracket_row)

        # 右括号行（含内部添加子节点按钮）
        self.right_bracket_row = QHBoxLayout()
        indent3 = QWidget()
        indent3.setFixedWidth((self.indent_level + 1) * 20)
        self.right_bracket_row.addWidget(indent3)
        self.right_bracket_row.addWidget(QLabel(")"))
        add_child_cond = QToolButton()
        add_child_cond.setText("＋条")
        add_child_cond.setToolTip("在组内添加条件")
        add_child_cond.clicked.connect(lambda: self.add_child_condition("AND"))
        self.right_bracket_row.addWidget(add_child_cond)
        add_child_group = QToolButton()
        add_child_group.setText("＋组")
        add_child_group.setToolTip("在组内添加条件组")
        add_child_group.clicked.connect(lambda: self.add_child_group("AND"))
        self.right_bracket_row.addWidget(add_child_group)
        self.right_bracket_row.addStretch()
        self.children_layout.addLayout(self.right_bracket_row)

    def add_child_condition(self, connector="AND"):
        """在组内添加一个叶子条件。"""
        widget = ConditionWidget(self.columns, self.indent_level + 1, connector, self)
        widget.removed.connect(self._on_child_removed)
        widget.add_sibling_condition.connect(self._add_condition_after_child)
        widget.add_sibling_group.connect(self._add_group_after_child)
        widget.connector_changed.connect(self.connector_changed.emit)
        insert_pos = self.children_layout.count() - 1  # 插入到右括号之前
        self.child_widgets.append(widget)
        self.children_layout.insertWidget(insert_pos, widget)
        self._update_children_last_state()
        self.connector_changed.emit()

    def add_child_group(self, connector="AND"):
        """在组内添加一个子条件组。"""
        widget = GroupWidget(self.columns, self.indent_level + 1, connector, self)
        widget.removed.connect(self._on_child_removed)
        widget.add_sibling_condition.connect(self._add_condition_after_child)
        widget.add_sibling_group.connect(self._add_group_after_child)
        widget.connector_changed.connect(self.connector_changed.emit)
        insert_pos = self.children_layout.count() - 1
        self.child_widgets.append(widget)
        self.children_layout.insertWidget(insert_pos, widget)
        self._update_children_last_state()
        self.connector_changed.emit()

    def _on_child_removed(self, child_widget):
        """移除指定的子节点 widget。"""
        if child_widget in self.child_widgets:
            self.child_widgets.remove(child_widget)
            self.children_layout.removeWidget(child_widget)
            child_widget.deleteLater()
            self._update_children_last_state()
            self.connector_changed.emit()

    def _add_condition_after_child(self):
        """在当前信号发送者 widget（子节点）之后插入一个条件。"""
        sender = self.sender()
        if sender and sender in self.child_widgets:
            idx = self.child_widgets.index(sender)
            new_widget = ConditionWidget(self.columns, self.indent_level + 1, "AND", self)
            new_widget.removed.connect(self._on_child_removed)
            new_widget.add_sibling_condition.connect(self._add_condition_after_child)
            new_widget.add_sibling_group.connect(self._add_group_after_child)
            new_widget.connector_changed.connect(self.connector_changed.emit)
            self.child_widgets.insert(idx + 1, new_widget)
            self._rebuild_children_layout()
        else:
            self.add_child_condition()
        self.connector_changed.emit()

    def _add_group_after_child(self):
        """在当前信号发送者 widget（子节点）之后插入一个条件组。"""
        sender = self.sender()
        if sender and sender in self.child_widgets:
            idx = self.child_widgets.index(sender)
            new_widget = GroupWidget(self.columns, self.indent_level + 1, "AND", self)
            new_widget.removed.connect(self._on_child_removed)
            new_widget.add_sibling_condition.connect(self._add_condition_after_child)
            new_widget.add_sibling_group.connect(self._add_group_after_child)
            new_widget.connector_changed.connect(self.connector_changed.emit)
            self.child_widgets.insert(idx + 1, new_widget)
            self._rebuild_children_layout()
        else:
            self.add_child_group()
        self.connector_changed.emit()

    def _rebuild_children_layout(self):
        """清空子节点区域并重新按顺序插入，保留左右括号行。"""
        for child in self.child_widgets:
            self.children_layout.removeWidget(child)
        insert_pos = self.children_layout.count() - 1
        for child in self.child_widgets:
            self.children_layout.insertWidget(insert_pos, child)
            insert_pos += 1
        self._update_children_last_state()

    def set_last(self, is_last):
        self._is_last = is_last
        self.connector_combo.setVisible(not is_last)

    def _update_children_last_state(self):
        """更新子节点列表的连接词显示（最后一个子节点隐藏连接词）。"""
        for i, child in enumerate(self.child_widgets):
            child.set_last(i == len(self.child_widgets) - 1)

    def get_node(self):
        """返回该控件对应的 FilterGroupNode（递归）。"""
        children = []
        connectors = []
        for child in self.child_widgets:
            children.append(child.get_node())
            connectors.append(child.get_connector())
        if len(connectors) == len(children):
            connectors = connectors[:-1]
        while len(connectors) < len(children) - 1:
            connectors.append("AND")
        return FilterGroupNode(children=children, connectors=connectors, enabled=self.enabled_check.isChecked())

    def get_connector(self):
        return self.connector_combo.currentText()


# -------------------------- 高级筛选对话框 --------------------------
class FilterDialog(QDialog):
    """高级筛选对话框，支持嵌套条件组和 SQL 预览，状态持久化。"""
    filterApplied = Signal(FilterGroupNode)

    def __init__(self, columns, parent=None, existing_root=None):
        super().__init__(parent)
        self.columns = columns
        self.setWindowTitle("高级筛选")
        self.setMinimumWidth(700)
        self.root_children = []  # 顶级节点列表
        self.setup_ui()
        if existing_root:
            self.load_state(existing_root)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 滚动区域（包含动态条件/组）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.root_layout = QVBoxLayout(self.scroll_content)
        self.root_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll)

        # 空白状态下显示的初始添加按钮（有节点后自动隐藏）
        self.empty_placeholder = QWidget()
        empty_layout = QHBoxLayout(self.empty_placeholder)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        btn_add_cond = QPushButton("＋ 添加条件")
        btn_add_cond.clicked.connect(lambda: self.add_root_condition())
        btn_add_group = QPushButton("＋ 添加条件组")
        btn_add_group.clicked.connect(lambda: self.add_root_group())
        empty_layout.addWidget(btn_add_cond)
        empty_layout.addWidget(btn_add_group)
        empty_layout.addStretch()
        self.root_layout.addWidget(self.empty_placeholder)
        self._update_empty_placeholder_visibility()

        # SQL 预览区域
        sql_label = QLabel("SQL 预览（只读）：")
        sql_label.setFont(QFont("Arial", 9, QFont.Bold))
        layout.addWidget(sql_label)
        self.sql_preview = QTextEdit()
        self.sql_preview.setReadOnly(True)
        self.sql_preview.setMaximumHeight(60)
        self.sql_preview.setFont(QFont("Consolas", 9))
        layout.addWidget(self.sql_preview)

        # 底部按钮栏
        btn_layout = QHBoxLayout()

        self.clear_btn = QPushButton("清空条件")
        self.clear_btn.clicked.connect(self.clear_all_conditions)
        btn_layout.addWidget(self.clear_btn)

        btn_layout.addStretch()
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.button(QDialogButtonBox.Ok).setText("应用筛选")
        btn_box.button(QDialogButtonBox.Cancel).setText("取消")
        btn_box.accepted.connect(self.apply_filter)
        btn_box.rejected.connect(self.reject)
        btn_layout.addWidget(btn_box)
        layout.addLayout(btn_layout)

        self.update_sql_preview()

    def _update_empty_placeholder_visibility(self):
        """控制空白占位按钮的显示/隐藏，当有根节点时隐藏。"""
        self.empty_placeholder.setVisible(len(self.root_children) == 0)

    def add_root_condition(self, connector="AND"):
        widget = ConditionWidget(self.columns, indent_level=0, connector=connector, parent=self)
        widget.removed.connect(lambda w: self._remove_root_child(w))
        widget.add_sibling_condition.connect(lambda: self._insert_root_condition_after(widget))
        widget.add_sibling_group.connect(lambda: self._insert_root_group_after(widget))
        widget.connector_changed.connect(self._on_root_changed)
        self.root_children.append(widget)
        self.root_layout.insertWidget(self.root_layout.count() - 1, widget)  # 插在占位符之前
        self._update_root_last_state()
        self._update_empty_placeholder_visibility()
        self._on_root_changed()

    def add_root_group(self, connector="AND"):
        widget = GroupWidget(self.columns, indent_level=0, connector=connector, parent=self)
        widget.removed.connect(lambda w: self._remove_root_child(w))
        widget.add_sibling_condition.connect(lambda: self._insert_root_condition_after(widget))
        widget.add_sibling_group.connect(lambda: self._insert_root_group_after(widget))
        widget.connector_changed.connect(self._on_root_changed)
        self.root_children.append(widget)
        self.root_layout.insertWidget(self.root_layout.count() - 1, widget)
        self._update_root_last_state()
        self._update_empty_placeholder_visibility()
        self._on_root_changed()

    def _remove_root_child(self, widget):
        if widget in self.root_children:
            self.root_children.remove(widget)
            self.root_layout.removeWidget(widget)
            widget.deleteLater()
            self._update_root_last_state()
            self._update_empty_placeholder_visibility()
            self._on_root_changed()

    def _insert_root_condition_after(self, after_widget):
        index = self.root_children.index(after_widget) if after_widget in self.root_children else -1
        new_widget = ConditionWidget(self.columns, indent_level=0, connector="AND", parent=self)
        new_widget.removed.connect(lambda w: self._remove_root_child(w))
        new_widget.add_sibling_condition.connect(lambda: self._insert_root_condition_after(new_widget))
        new_widget.add_sibling_group.connect(lambda: self._insert_root_group_after(new_widget))
        new_widget.connector_changed.connect(self._on_root_changed)
        if 0 <= index < len(self.root_children):
            self.root_children.insert(index + 1, new_widget)
            self._rebuild_root_layout()
        else:
            self.root_children.append(new_widget)
            self.root_layout.insertWidget(self.root_layout.count() - 1, new_widget)
        self._update_root_last_state()
        self._on_root_changed()

    def _insert_root_group_after(self, after_widget):
        index = self.root_children.index(after_widget) if after_widget in self.root_children else -1
        new_widget = GroupWidget(self.columns, indent_level=0, connector="AND", parent=self)
        new_widget.removed.connect(lambda w: self._remove_root_child(w))
        new_widget.add_sibling_condition.connect(lambda: self._insert_root_condition_after(new_widget))
        new_widget.add_sibling_group.connect(lambda: self._insert_root_group_after(new_widget))
        new_widget.connector_changed.connect(self._on_root_changed)
        if 0 <= index < len(self.root_children):
            self.root_children.insert(index + 1, new_widget)
            self._rebuild_root_layout()
        else:
            self.root_children.append(new_widget)
            self.root_layout.insertWidget(self.root_layout.count() - 1, new_widget)
        self._update_root_last_state()
        self._on_root_changed()

    def _rebuild_root_layout(self):
        """重新按顺序放置根节点，并保留占位符在最后。"""
        for child in self.root_children:
            self.root_layout.removeWidget(child)
        insert_pos = 0
        for child in self.root_children:
            self.root_layout.insertWidget(insert_pos, child)
            insert_pos += 1
        self._update_root_last_state()

    def _update_root_last_state(self):
        for i, child in enumerate(self.root_children):
            child.set_last(i == len(self.root_children) - 1)

    def _on_root_changed(self):
        self.update_sql_preview()

    def clear_all_conditions(self):
        """清空所有筛选条件。"""
        while self.root_children:
            child = self.root_children.pop()
            self.root_layout.removeWidget(child)
            child.deleteLater()
        self._update_root_last_state()
        self._update_empty_placeholder_visibility()
        self._on_root_changed()

    def update_sql_preview(self):
        """根据根节点生成 SQL 并显示在预览区。"""
        if not self.root_children:
            self.sql_preview.clear()
            return
        children = []
        connectors = []
        for child in self.root_children:
            children.append(child.get_node())
            connectors.append(child.get_connector())
        if len(connectors) == len(children):
            connectors = connectors[:-1]
        tmp_root = FilterGroupNode(children=children, connectors=connectors, enabled=True)
        sql = self._build_sql(tmp_root)
        self.sql_preview.setPlainText(sql)

    def _build_sql(self, node):
        """递归生成 SQL WHERE 表达式字符串。"""
        if isinstance(node, FilterConditionNode):
            if not node.enabled:
                return "1=1"
            col = node.column
            op = node.operator
            val = node.value
            if op == "is_null":
                return f"{col} IS NULL"
            elif op == "is_not_null":
                return f"{col} IS NOT NULL"
            elif op == "icontains":
                return f"LOWER({col}) LIKE '%{val}%'"
            elif op == "contains":
                return f"{col} LIKE '%{val}%'"
            elif op == "not_contains":
                return f"{col} NOT LIKE '%{val}%'"
            else:
                return f"{col} {op} '{val}'"
        elif isinstance(node, FilterGroupNode):
            if not node.enabled:
                return "1=1"
            if not node.children:
                return "1=1"
            parts = []
            for i, child in enumerate(node.children):
                child_sql = self._build_sql(child)
                if i == 0:
                    parts.append(child_sql)
                else:
                    conn = node.connectors[i - 1] if i - 1 < len(node.connectors) else "AND"
                    parts.append(f" {conn} {child_sql}")
            return f"({' '.join(parts)})"
        return "1=1"

    def apply_filter(self):
        """组装根组节点并提交筛选。"""
        children = []
        connectors = []
        for child in self.root_children:
            children.append(child.get_node())
            connectors.append(child.get_connector())
        if len(connectors) == len(children):
            connectors = connectors[:-1]
        root_node = FilterGroupNode(children=children, connectors=connectors, enabled=True)
        self.filterApplied.emit(root_node)
        self.accept()

    def load_state(self, root_node):
        """根据已有的 FilterGroupNode 重建 UI。"""
        # 清空当前所有根节点
        self.clear_all_conditions_internal()
        if not isinstance(root_node, FilterGroupNode):
            self._update_empty_placeholder_visibility()
            return

        for i, child_node in enumerate(root_node.children):
            connector = root_node.connectors[i - 1] if i >= 1 else "AND"
            if isinstance(child_node, FilterConditionNode):
                self._add_root_condition_from_node(child_node, connector)
            elif isinstance(child_node, FilterGroupNode):
                self._add_root_group_from_node(child_node, connector)
        self._update_root_last_state()
        self._update_empty_placeholder_visibility()
        self._on_root_changed()

    def clear_all_conditions_internal(self):
        """仅清除所有根节点 widget，不操作占位符。"""
        while self.root_children:
            child = self.root_children.pop()
            self.root_layout.removeWidget(child)
            child.deleteLater()
        self._update_root_last_state()

    def _add_root_condition_from_node(self, node, connector):
        """根据 FilterConditionNode 在根级添加一个条件控件。"""
        widget = ConditionWidget(self.columns, indent_level=0, connector=connector, parent=self)
        widget.enabled_check.setChecked(node.enabled)
        col_idx = widget.col_combo.findText(node.column)
        if col_idx >= 0:
            widget.col_combo.setCurrentIndex(col_idx)
        op_text = [k for k, v in ConditionWidget.OPERATORS.items() if v == node.operator]
        if op_text:
            widget.op_combo.setCurrentText(op_text[0])
        if node.value is not None:
            widget.value_edit.setText(str(node.value))
        self._finalize_root_widget(widget)

    def _add_root_group_from_node(self, node, connector):
        """根据 FilterGroupNode 在根级添加一个条件组控件。"""
        widget = GroupWidget(self.columns, indent_level=0, connector=connector, parent=self)
        widget.enabled_check.setChecked(node.enabled)
        self._populate_group(widget, node)
        self._finalize_root_widget(widget)

    def _populate_group(self, group_widget, group_node):
        """递归向 GroupWidget 添加子节点。"""
        for i, child_node in enumerate(group_node.children):
            connector = group_node.connectors[i - 1] if i >= 1 else "AND"
            if isinstance(child_node, FilterConditionNode):
                group_widget.add_child_condition(connector)
                child_widget = group_widget.child_widgets[-1]
                child_widget.enabled_check.setChecked(child_node.enabled)
                col_idx = child_widget.col_combo.findText(child_node.column)
                if col_idx >= 0:
                    child_widget.col_combo.setCurrentIndex(col_idx)
                op_text = [k for k, v in ConditionWidget.OPERATORS.items() if v == child_node.operator]
                if op_text:
                    child_widget.op_combo.setCurrentText(op_text[0])
                if child_node.value is not None:
                    child_widget.value_edit.setText(str(child_node.value))
            elif isinstance(child_node, FilterGroupNode):
                group_widget.add_child_group(connector)
                child_widget = group_widget.child_widgets[-1]
                child_widget.enabled_check.setChecked(child_node.enabled)
                self._populate_group(child_widget, child_node)
        group_widget._update_children_last_state()

    def _finalize_root_widget(self, widget):
        """为根级控件连接标准信号。"""
        widget.removed.connect(lambda w: self._remove_root_child(w))
        widget.add_sibling_condition.connect(lambda: self._insert_root_condition_after(widget))
        widget.add_sibling_group.connect(lambda: self._insert_root_group_after(widget))
        widget.connector_changed.connect(self._on_root_changed)
        self.root_children.append(widget)
        self.root_layout.insertWidget(self.root_layout.count() - 1, widget)
