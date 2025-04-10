import os

from PyQt5.QtCore import QDir, Qt, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QContextMenuEvent, QKeyEvent
from PyQt5.QtWidgets import QFileSystemModel, QTableView

from cfg import JsonData
from signals import SignalsApp
from utils import Utils

from ._actions import (ChangeView, CopyPath, FavAdd, FavRemove, Info,
                       RevealInFinder)
from ._base import BaseMethods, UMenu, BaseSignals
from ._finder_items import LoadingWid


class ListFileSystem(QTableView):
    col: int = 0
    order: int = 0
    sizes: list = [250, 100, 100, 150]
    last_selection: str = None

    # сигналы должны быть идентичны grid.py > Grid
    new_history_item = pyqtSignal(str)
    fav_cmd_sig = pyqtSignal(tuple)
    load_st_grid_sig = pyqtSignal(tuple)
    bar_bottom_update = pyqtSignal(tuple)
    move_slider_sig = pyqtSignal(int)
    change_view_sig = pyqtSignal(int)

    def __init__(self, main_dir: str):
        QTableView.__init__(self)
        BaseMethods.__init__(self)

        self.main_dir = main_dir

        self.loading_lbl = LoadingWid(parent=self)
        Utils.center_win(self, self.loading_lbl)
        self.show()

        self.setSelectionBehavior(QTableView.SelectRows)
        self.setSortingEnabled(True)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().sectionClicked.connect(self.save_sort_settings)
        self.doubleClicked.connect(self.double_clicked)

        self._model = QFileSystemModel()
        self._model.setRootPath(self.main_dir)
        self._model.setFilter(QDir.NoDotAndDotDot | QDir.AllEntries)

        self.setModel(self._model)
        self.setRootIndex(self._model.index(self.main_dir))

        self.sortByColumn(ListFileSystem.col, ListFileSystem.order)
        for i in range(0, 4):
            self.setColumnWidth(i, ListFileSystem.sizes[i])

        self.loading_lbl.hide()

    def double_clicked(self, index):
        path = self._model.filePath(index)

        if os.path.isdir(path):
            self.setCurrentIndex(index)
            self.load_st_grid_sig.emit((path, None))

    def save_sort_settings(self, index):
        ListFileSystem.col = index
        ListFileSystem.order = self.horizontalHeader().sortIndicatorOrder()
        self.sortByColumn(ListFileSystem.col, ListFileSystem.order)

    def rearrange(self, *args, **kwargs):
        ...

    def order_(self, *args, **kwargs):
        ...

    def filter_(self, *args, **kwargs):
        ...

    def resize_(self, *args, **kwargs):
        ...

    def select_new_widget(self, *args, **kwargs):
        ...

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        index = self.currentIndex()
        path = self._model.filePath(index)
        path = os.path.abspath(path)
        ListFileSystem.last_selection = path
        ListFileSystem.sizes = [self.columnWidth(i) for i in range(0, 4)]
        return super().closeEvent(a0)

    def contextMenuEvent(self, event: QContextMenuEvent):

        index = self.indexAt(event.pos())

        if not index.isValid():
            return

        menu = UMenu(self)

        src = self._model.filePath(index)
        index = self._model.index(src)

        info = Info(menu, src)
        menu.addAction(info)

        open_finder_action = RevealInFinder(parent=menu, src=src)
        menu.addAction(open_finder_action)

        copy_path_action = CopyPath(menu, src)
        menu.addAction(copy_path_action)

        menu.addSeparator()

        if os.path.isdir(src):
            if src in JsonData.favs:
                cmd_ = lambda: self.fav_cmd_sig.emit(("del", src))
                fav_action = FavRemove(menu, src)
                fav_action._clicked.connect(cmd_)
                menu.addAction(fav_action)
            else:
                cmd_ = lambda: self.fav_cmd_sig.emit(("add", src))
                fav_action = FavAdd(menu, src)
                fav_action._clicked.connect(cmd_)
                menu.addAction(fav_action)

        menu.addSeparator()

        change_view = ChangeView(menu)
        change_view.load_st_grid_sig.connect(self.load_st_grid_sig.emit)
        menu.addMenu(change_view)

        menu.show_custom()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.modifiers() & Qt.KeyboardModifier.ControlModifier:

            if a0.key() == Qt.Key.Key_Up:
                root = os.path.dirname(self.main_dir)
                if root != os.sep:
                    self.new_history_item.emit(root)
                    self.load_st_grid_sig.emit((root, None))
                    return

            elif a0.key() == Qt.Key.Key_Down:
                index = self.currentIndex()
                self.double_clicked(index)
                return

        elif a0.key() in (Qt.Key.Key_Return, Qt.Key.Key_Space):
            index = self.currentIndex()
            self.double_clicked(index)
            return

        return super().keyPressEvent(a0)
