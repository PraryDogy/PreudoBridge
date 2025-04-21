import os

from PyQt5.QtCore import QDir, Qt
from PyQt5.QtGui import QCloseEvent, QContextMenuEvent, QKeyEvent
from PyQt5.QtWidgets import QFileSystemModel, QTableView

from cfg import JsonData

from ._base_items import UMenu, UTableView
from .actions import (ChangeViewMenu, CopyPath, FavAdd, FavRemove, Info,
                      RevealInFinder)
from .finder_items import LoadingWid
from .info_win import InfoWin


class GridList(UTableView):
    col: int = 0
    order: int = 0
    sizes: list = [250, 100, 100, 150]

    def __init__(self, main_dir: str, view_index: int):
        super().__init__()

        self.main_dir = main_dir
        self.view_index = view_index

        self.loading_lbl = LoadingWid(parent=self)
        self.loading_lbl.center(self)
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

        self.sortByColumn(GridList.col, GridList.order)
        for i in range(0, 4):
            self.setColumnWidth(i, GridList.sizes[i])

        self.loading_lbl.hide()

    def double_clicked(self, index):
        path = self._model.filePath(index)

        if os.path.isdir(path):
            self.setCurrentIndex(index)
            self.load_st_grid_sig.emit((path, None))

    def save_sort_settings(self, index):
        GridList.col = index
        GridList.order = self.horizontalHeader().sortIndicatorOrder()
        self.sortByColumn(GridList.col, GridList.order)

    def rearrange(self, *args, **kwargs):
        ...

    def sort_(self, *args, **kwargs):
        ...

    def filter_(self, *args, **kwargs):
        ...

    def resize_(self, *args, **kwargs):
        ...

    def select_new_widget(self, *args, **kwargs):
        ...

    def win_info_cmd(self, src: str):
        self.win_info = InfoWin(src)
        self.win_info.center(self.window())
        self.win_info.show()

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        index = self.currentIndex()
        path = self._model.filePath(index)
        path = os.path.abspath(path)
        GridList.sizes = [self.columnWidth(i) for i in range(0, 4)]
        return super().closeEvent(a0)

    def contextMenuEvent(self, event: QContextMenuEvent):
        index = self.indexAt(event.pos())

        menu = UMenu(parent=self)

        src = self._model.filePath(index)
        index = self._model.index(src)

        if not src:
            src = self.main_dir

        info = Info(menu)
        info.triggered.connect(lambda: self.win_info_cmd(src))
        menu.addAction(info)

        open_finder_action = RevealInFinder(menu, src)
        menu.addAction(open_finder_action)

        copy_path_action = CopyPath(menu, src)
        menu.addAction(copy_path_action)

        menu.addSeparator()

        if os.path.isdir(src):
            if src in JsonData.favs:
                cmd_ = lambda: self.fav_cmd_sig.emit(("del", src))
                fav_action = FavRemove(menu)
                fav_action.triggered.connect(cmd_)
                menu.addAction(fav_action)
            else:
                cmd_ = lambda: self.fav_cmd_sig.emit(("add", src))
                fav_action = FavAdd(menu)
                fav_action.triggered.connect(cmd_)
                menu.addAction(fav_action)

        menu.addSeparator()

        change_view = ChangeViewMenu(menu, self.view_index)
        change_view.change_view_sig.connect(self.change_view_sig.emit)
        menu.addMenu(change_view)

        menu.show_()

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
