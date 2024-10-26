import os
import subprocess

from PyQt5.QtCore import QDir, Qt
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QAction, QFileSystemModel, QMenu, QTableView

from cfg import IMG_EXT, JsonData
from signals import SIGNALS
from utils import Utils

from ._base import BaseTableView
from ._thumb import Thumb
from .win_img_view import WinImgView


class Sort:
    column = 0
    order = 0


class ListStandart(BaseTableView):
    def __init__(self):
        super().__init__()

        self._model = QFileSystemModel()
        self._model.setRootPath(JsonData.root)
        self._model.setFilter(QDir.NoDotAndDotDot | QDir.AllEntries)

        self.setModel(self._model)
        self.setRootIndex(self._model.index(JsonData.root))

        self.setSelectionBehavior(QTableView.SelectRows)
        self.setSortingEnabled(True)
        self.verticalHeader().setVisible(False)
        self.sortByColumn(Sort.column, Sort.order)

        self.setColumnWidth(0, 250)
        self.setColumnWidth(1, 100)
        self.setColumnWidth(2, 100)
        self.setColumnWidth(3, 150)

        self.horizontalHeader().sectionClicked.connect(self.save_sort_settings)
        self.doubleClicked.connect(self.double_clicked)

    def double_clicked(self, index):
        path = self._model.filePath(index)
        path = os.path.abspath(path)

        if os.path.isdir(path):
            self.setCurrentIndex(index)
            SIGNALS.load_standart_grid.emit(path)

        elif path.endswith(IMG_EXT):
            thumbnail = Thumb()
            self.win = WinImgView(path, {path: thumbnail})
            self.win.show()

    def save_sort_settings(self, index):
        Sort.column = index
        Sort.order = self.horizontalHeader().sortIndicatorOrder()
        self.sortByColumn(Sort.column, Sort.order)

    def open_in_finder(self, path: str):
        subprocess.call(["open", "-R", path])

    def rearrange_grid(self, *args, **kwargs):
        ...

    def order_grid(self, *args, **kwargs):
        ...

    def filter_grid(self, *args, **kwargs):
        ...

    def resize_grid(self, *args, **kwargs):
        ...

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return

        menu = QMenu(self)
        src = self._model.filePath(index)
        index = self._model.index(src)

        open_finder_action = QAction("Просмотр", self)
        open_finder_action.triggered.connect(lambda: self.double_clicked(index))
        menu.addAction(open_finder_action)

        menu.addSeparator()

        open_finder_action = QAction("Показать в Finder", self)
        open_finder_action.triggered.connect(lambda: self.open_in_finder(src))
        menu.addAction(open_finder_action)

        copy_path_action = QAction("Скопировать путь до папки", self)
        copy_path_action.triggered.connect(lambda: Utils.copy_path(src))
        menu.addAction(copy_path_action)

        menu.addSeparator()

        if os.path.isdir(src):
            if src in JsonData.favs:
                fav_action = QAction("Удалить из избранного", self)
                fav_action.triggered.connect(lambda: SIGNALS.del_fav.emit(src))
                menu.addAction(fav_action)
            else:
                fav_action = QAction("Добавить в избранное", self)
                fav_action.triggered.connect(lambda: SIGNALS.add_fav.emit(src))
                menu.addAction(fav_action)

        menu.exec_(self.mapToGlobal(event.pos()))

    def keyPressEvent(self, e: QKeyEvent | None) -> None:
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Space):
            index = self.currentIndex()
            self.double_clicked(index)
        return super().keyPressEvent(e)
