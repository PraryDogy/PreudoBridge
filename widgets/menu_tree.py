from PyQt5.QtCore import QDir, Qt, pyqtSignal
from PyQt5.QtWidgets import QFileSystemModel, QTreeView

from cfg import JsonData
from signals import SignalsApp

from ._actions import CopyPath, FavAdd, FavRemove, RevealInFinder, View
from ._base import UMenu


class MenuTree(QTreeView):
    new_history_item = pyqtSignal(str)
    fav_cmd_sig = pyqtSignal(tuple)
    load_st_grid_sig = pyqtSignal(tuple)

    def __init__(self):
        super().__init__()

        self.horizontalScrollBar().setDisabled(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

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
        self.new_history_item.emit(path)
        self.load_st_grid_sig.emit((path, None))

        self.expand(index)

    def expand_path(self, root: str):
        index = self.c_model.index(root)
        self.setCurrentIndex(index)
        self.expand(index)

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return

        menu = UMenu(self)
        src = self.c_model.filePath(index)
        index = self.c_model.index(src)

        cmd_ = lambda: self.one_clicked(index)
        open_finder_action = View(menu, src)
        open_finder_action._clicked.connect(cmd_)
        menu.addAction(open_finder_action)

        menu.addSeparator()

        open_finder_action = RevealInFinder(menu, src)
        menu.addAction(open_finder_action)

        copy_path_action = CopyPath(menu, src)
        menu.addAction(copy_path_action)

        menu.addSeparator()

        favs: dict = JsonData.favs
        if src in favs:
            cmd_ = lambda: self.fav_cmd_sig.emit(("del", src))
            fav_action = FavRemove(menu, src)
            fav_action._clicked.connect(cmd_)
            menu.addAction(fav_action)
        else:
            cmd_ = lambda: self.fav_cmd_sig.emit(("add", src))
            fav_action = FavAdd(menu, src)
            fav_action._clicked.connect(cmd_)
            menu.addAction(fav_action)

        menu.exec_(self.mapToGlobal(event.pos()))
