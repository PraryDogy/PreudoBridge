import os

from PyQt5.QtCore import QDir, Qt, pyqtSignal
from PyQt5.QtWidgets import QFileSystemModel, QTreeView

from cfg import JsonData, Static

from ._base_items import MainWinItem, UMenu
from .actions import (CopyName, CopyPath, FavAdd, FavRemove, OpenInNewWindow,
                      RevealInFinder, View)


class TreeMenu(QTreeView):
    new_history_item = pyqtSignal(str)
    load_st_grid_sig = pyqtSignal()
    open_in_new_window = pyqtSignal(str)
    del_fav = pyqtSignal(str)
    add_fav = pyqtSignal(str)

    def __init__(self, main_win_item: MainWinItem):
        super().__init__()
        self.main_win_item = main_win_item

        self.horizontalScrollBar().setDisabled(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.c_model = QFileSystemModel()
        self.c_model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot)
        self.c_model.setRootPath(os.sep + Static.VOLUMES)
        self.setModel(self.c_model)
        self.setRootIndex(self.c_model.index(os.sep + Static.VOLUMES))

        self.setHeaderHidden(True)
        for i in range(1, self.c_model.columnCount()):
            self.setColumnHidden(i, True)

        self.setIndentation(10)
        self.setUniformRowHeights(True)

        self.clicked.connect(self.one_clicked)

    def one_clicked(self, index):
        path = self.c_model.filePath(index)
        self.setCurrentIndex(index)
        self.new_history_item.emit(path)
        self.main_win_item.main_dir = path
        self.load_st_grid_sig.emit()

        self.expand(index)

    def expand_path(self, root: str):
        index = self.c_model.index(root)
        self.setCurrentIndex(index)
        self.expand(index)

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return

        menu = UMenu(parent=self)
        src = self.c_model.filePath(index)
        index = self.c_model.index(src)

        cmd_ = lambda: self.one_clicked(index)
        open_finder_action = View(menu)
        open_finder_action.triggered.connect(cmd_)
        menu.addAction(open_finder_action)

        if os.path.isdir(src):
            new_win = OpenInNewWindow(menu)
            new_win.triggered.connect(lambda: self.open_in_new_window.emit(src))
            menu.addAction(new_win)

        menu.addSeparator()

        open_finder_action = RevealInFinder(menu, src)
        menu.addAction(open_finder_action)

        copy_path_action = CopyPath(menu, src)
        menu.addAction(copy_path_action)

        copy_name = CopyName(menu, os.path.basename(src))
        menu.addAction(copy_name)

        menu.addSeparator()

        favs: dict = JsonData.favs
        if src in favs:
            cmd_ = lambda: self.del_fav.emit(src)
            fav_action = FavRemove(menu)
            fav_action.triggered.connect(cmd_)
            menu.addAction(fav_action)
        else:
            cmd_ = lambda: self.add_fav.emit(src)
            fav_action = FavAdd(menu)
            fav_action.triggered.connect(cmd_)
            menu.addAction(fav_action)

        menu.show_()
