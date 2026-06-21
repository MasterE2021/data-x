from PySide6 import QtCore
from pathlib import Path


# 动态加载qss
class QSSManager(QtCore.QObject):
    """QSS 动态加载管理器"""
    styleChanged = QtCore.Signal(str)

    def __init__(self, file_paths: list[str]):
        super().__init__()
        # 1. 转换为绝对路径，避免由于工作目录变动导致找不到文件
        self.files = [Path(f).resolve() for f in file_paths]
        self.watcher = QtCore.QFileSystemWatcher(self)

        # 2. 初始化监听
        self._setup_watcher()
        self.watcher.fileChanged.connect(self._on_file_changed)

    def _setup_watcher(self):
        """将存在的样式文件加入监听"""
        for f in self.files:
            if f.exists() and str(f) not in self.watcher.files():
                self.watcher.addPath(str(f))

    def _on_file_changed(self, path: str):
        """文件变动时的回调"""
        # 某些编辑器（如VSCode）保存时会使用“安全保存”（先删除后新建），这会导致监听掉线。
        # 此时需要确认文件存在并重新加入监听。
        if Path(path).exists() and path not in self.watcher.files():
            self.watcher.addPath(path)

        # 发射最新的 QSS 文本信号
        self.styleChanged.emit(self.load())

    def load(self) -> str:
        """读取并合并所有 QSS 文件内容"""
        # 使用生成器表达式，代码更简洁
        return "\n".join(
            f.read_text(encoding="utf-8") for f in self.files if f.exists()
        )
