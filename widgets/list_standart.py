import subprocess

from PyQt5.QtCore import QDir, Qt, pyqtSignal
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QAction, QFileSystemModel, QMenu, QTableView

from cfg import Config
from utils import Utils

from .grid_base import GridMethods


class Sort:
    column = 0
    order = 0


class ListStandart(QTableView, GridMethods):
    folders_tree_clicked = pyqtSignal(str)
    add_to_favs_clicked = pyqtSignal(str)
    del_favs_clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        self._model = QFileSystemModel()
        self._model.setRootPath(Config.json_data.get("root"))
        self._model.setFilter(QDir.NoDotAndDotDot | QDir.AllEntries)

        self.setModel(self._model)
        self.setRootIndex(self._model.index(Config.json_data.get("root")))

        self.setSelectionBehavior(QTableView.SelectRows)
        self.setSortingEnabled(True)
        self.verticalHeader().setVisible(False)
        self.sortByColumn(Sort.column, Sort.order)

        self.setColumnWidth(0, 250)
        self.setColumnWidth(1, 100)
        self.setColumnWidth(2, 100)
        self.setColumnWidth(3, 150)

        self.horizontalHeader().sectionClicked.connect(self._save_sort_settings)
        self.doubleClicked.connect(self._d_clicked)

    def _d_clicked(self, index):
        path = self._model.filePath(index)
        self.setCurrentIndex(index)
        self.folders_tree_clicked.emit(path)

    def _save_sort_settings(self, index):
        Sort.column = index
        Sort.order = self.horizontalHeader().sortIndicatorOrder()
        self.sortByColumn(Sort.column, Sort.order)

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return

        menu = QMenu(self)
        src = self._model.filePath(index)
        index = self._model.index(src)

        open_finder_action = QAction("Просмотр", self)
        open_finder_action.triggered.connect(lambda: self._d_clicked(index))
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

    def stop_and_wait_threads(self):
        ...

    def move_to_wid(self, path: str):
        ...