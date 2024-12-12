import os

from PyQt5.QtCore import QDir, QPoint, Qt
from PyQt5.QtGui import QCloseEvent, QContextMenuEvent, QKeyEvent
from PyQt5.QtWidgets import QFileSystemModel, QMenu, QTableView

from cfg import JsonData
from signals import SignalsApp
from utils import Utils

from ._actions import (ChangeView, CopyPath, FavAdd, FavRemove, Info,
                       RevealInFinder)
from ._base import BaseMethods
from ._finder_items import LoadingWid


class ListFileSystem(QTableView):
    col: int = 0
    order: int = 0
    sizes: list = [250, 100, 100, 150]
    last_selection: str = None

    def __init__(self):
        QTableView.__init__(self)
        BaseMethods.__init__(self)

        self.loading_lbl = LoadingWid(parent=self)
        Utils.center_win(self, self.loading_lbl)
        self.show()

        self.setSelectionBehavior(QTableView.SelectRows)
        self.setSortingEnabled(True)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().sectionClicked.connect(self.save_sort_settings)
        self.doubleClicked.connect(self.double_clicked)

        self._model = QFileSystemModel()
        self._model.setRootPath(JsonData.root)
        self._model.setFilter(QDir.NoDotAndDotDot | QDir.AllEntries)

        self.setModel(self._model)
        self.setRootIndex(self._model.index(JsonData.root))

        self.sortByColumn(ListFileSystem.col, ListFileSystem.order)
        for i in range(0, 4):
            self.setColumnWidth(i, ListFileSystem.sizes[i])

        self.loading_lbl.hide()

    def double_clicked(self, index):
        path = self._model.filePath(index)

        if os.path.isdir(path):
            self.setCurrentIndex(index)
            SignalsApp.all_.load_normal_mode.emit(path)

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

        menu = QMenu(self)

        src = self._model.filePath(index)
        index = self._model.index(src)

        info = Info(menu, src)
        menu.addAction(info)

        open_finder_action = RevealInFinder(menu, src)
        menu.addAction(open_finder_action)

        copy_path_action = CopyPath(menu, src)
        menu.addAction(copy_path_action)

        menu.addSeparator()

        if os.path.isdir(src):
            if src in JsonData.favs:
                cmd_ = lambda: SignalsApp.all_.fav_cmd.emit({"cmd": "del", "src": src})
                fav_action = FavRemove(menu, src)
                fav_action._clicked.connect(cmd_)
                menu.addAction(fav_action)
            else:
                cmd_ = lambda: SignalsApp.all_.fav_cmd.emit({"cmd": "add", "src": src})
                fav_action = FavAdd(menu, src)
                fav_action._clicked.connect(cmd_)
                menu.addAction(fav_action)

        menu.addSeparator()

        change_view = ChangeView(menu, JsonData.root)
        menu.addMenu(change_view)

        coords = self.mapToGlobal(event.pos())
        # coords = QPoint(coords.x(), coords.y() + 30)
        menu.exec_(coords)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.modifiers() & Qt.KeyboardModifier.ControlModifier:

            if a0.key() == Qt.Key.Key_Up:
                root = os.path.dirname(JsonData.root)
                if root != os.sep:
                    SignalsApp.all_.new_history.emit(root)
                    SignalsApp.all_.load_normal_mode.emit(root)
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
