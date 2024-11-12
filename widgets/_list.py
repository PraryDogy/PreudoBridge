import os

from PyQt5.QtCore import QDir, Qt
from PyQt5.QtGui import QCloseEvent, QKeyEvent
from PyQt5.QtWidgets import QFileSystemModel, QMenu, QTableView

from cfg import JsonData
from signals import SignalsApp

from ._actions import CopyPath, FavAdd, FavRemove, RevealInFinder
from ._base import BaseMethods


class Shared:
    column = 0
    order = 0
    sizes: list = [250, 100, 100, 150]


class Selected:
    src: str = None


class ListStandart(QTableView):
    def __init__(self):
        QTableView.__init__(self)
        BaseMethods.__init__(self)

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

        self.sortByColumn(Shared.column, Shared.order)
        for i in range(0, 4):
            self.setColumnWidth(i, Shared.sizes[i])

    def double_clicked(self, index):
        path = self._model.filePath(index)
        path = os.path.abspath(path)

        if os.path.isdir(path):
            self.setCurrentIndex(index)
            SignalsApp.all.load_standart_grid.emit(path)

    def save_sort_settings(self, index):
        Shared.column = index
        Shared.order = self.horizontalHeader().sortIndicatorOrder()
        self.sortByColumn(Shared.column, Shared.order)

    def rearrange(self, *args, **kwargs):
        ...

    def order_(self, *args, **kwargs):
        ...

    def filter_(self, *args, **kwargs):
        ...

    def resize_(self, *args, **kwargs):
        ...

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        index = self.currentIndex()
        path = self._model.filePath(index)
        path = os.path.abspath(path)
        Selected.src = path
        Shared.sizes = [self.columnWidth(i) for i in range(0, 4)]

        return super().closeEvent(a0)

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return

        menu = QMenu(self)
        src = self._model.filePath(index)
        index = self._model.index(src)

        open_finder_action = RevealInFinder(menu, src)
        menu.addAction(open_finder_action)

        copy_path_action = CopyPath(menu, src)
        menu.addAction(copy_path_action)

        menu.addSeparator()

        if os.path.isdir(src):
            if src in JsonData.favs:
                cmd_ = lambda: SignalsApp.all.fav_cmd.emit("del", src)
                fav_action = FavRemove(menu, src)
                fav_action._clicked.connect(cmd_)
                menu.addAction(fav_action)
            else:
                cmd_ = lambda: SignalsApp.all.fav_cmd.emit("add", src)
                fav_action = FavAdd(menu, src)
                fav_action._clicked.connect(cmd_)
                menu.addAction(fav_action)

        menu.exec_(self.mapToGlobal(event.pos()))

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.modifiers() & Qt.KeyboardModifier.ControlModifier:

            if a0.key() == Qt.Key.Key_Up:
                root = os.path.dirname(JsonData.root)
                if root != os.sep:
                    SignalsApp.all.new_history.emit(root)
                    SignalsApp.all.load_standart_grid.emit(root)
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
