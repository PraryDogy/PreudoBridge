import subprocess

from PyQt5.QtCore import QDir, pyqtSignal
from PyQt5.QtWidgets import QAction, QFileSystemModel, QMenu, QTreeView

from cfg import Config
from utils import Utils


class TreeFolders(QTreeView):
    folders_tree_clicked = pyqtSignal(str)
    add_to_favs_clicked = pyqtSignal(str)
    del_favs_clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        self.c_model = QFileSystemModel()
        self.c_model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot)
        self.c_model.setRootPath("/Volumes")
        self.setModel(self.c_model)
        self.setRootIndex(self.c_model.index("/Volumes"))

        self.setHeaderHidden(True)
        for i in range(1, self.c_model.columnCount()):
            self.setColumnHidden(i, True)

        self.setIndentation(10)
        self.setUniformRowHeights(True)

        self.clicked.connect(self.one_clicked)

    def one_clicked(self, index):
        path = self.c_model.filePath(index)
        self.setCurrentIndex(index)
        self.folders_tree_clicked.emit(path)
        self.expand(index)

    def expand_path(self, root: str):
        index = self.c_model.index(root)
        self.setCurrentIndex(index)
        self.expand(index)

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return

        menu = QMenu(self)
        src = self.c_model.filePath(index)
        index = self.c_model.index(src)

        open_finder_action = QAction("Просмотр", self)
        open_finder_action.triggered.connect(lambda: self.one_clicked(index))
        menu.addAction(open_finder_action)

        menu.addSeparator()

        open_finder_action = QAction("Показать в Finder", self)
        open_finder_action.triggered.connect(lambda: self.open_in_finder(src))
        menu.addAction(open_finder_action)

        copy_path_action = QAction("Скопировать путь до папки", self)
        copy_path_action.triggered.connect(lambda: Utils.copy_path(src))
        menu.addAction(copy_path_action)

        menu.addSeparator()

        favs: dict = Config.json_data.get("favs")
        if src in favs:
            fav_action = QAction("Удалить из избранного", self)
            fav_action.triggered.connect(lambda: self.del_favs_clicked.emit(src))
            menu.addAction(fav_action)
        else:
            fav_action = QAction("Добавить в избранное", self)
            fav_action.triggered.connect(lambda: self.add_to_favs_clicked.emit(src))
            menu.addAction(fav_action)

        menu.exec_(self.mapToGlobal(event.pos()))

    def open_in_finder(self, path: str):
        subprocess.call(["open", "-R", path])
