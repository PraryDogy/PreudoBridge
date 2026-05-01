import os

from PyQt5.QtCore import QDir, Qt, pyqtSignal
from PyQt5.QtWidgets import QAbstractItemView, QFileSystemModel, QTreeView

from cfg import JsonData
from system.items import MainWinItem, NameUrlItem

from ._base_widgets import UMenu
from .actions import Actions


class MenuTree(QTreeView):
    new_history_item = pyqtSignal(str)
    load_st_grid_sig = pyqtSignal(str)
    new_main_win = pyqtSignal(str)
    remove_fav = pyqtSignal(NameUrlItem)
    add_fav = pyqtSignal(NameUrlItem)
    reveal = pyqtSignal(list)
    copy_urls = pyqtSignal(list)
    copy_names = pyqtSignal(list)

    volumes = "/Volumes"
    # предполагает что системный диск всегда будет первым
    macintosh = [i for i in os.scandir(volumes)][0].path

    def __init__(self, main_win_item: MainWinItem):
        super().__init__()
        self.main_win_item = main_win_item

        self.horizontalScrollBar().setDisabled(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.c_model = QFileSystemModel()
        self.c_model.setFilter(
            QDir.Filter.AllDirs | 
            QDir.Filter.NoDotAndDotDot
        )
        self.c_model.setRootPath(self.volumes)
        self.setModel(self.c_model)
        self.setRootIndex(self.c_model.index(self.volumes))

        self.setHeaderHidden(True)
        for i in range(1, self.c_model.columnCount()):
            self.setColumnHidden(i, True)

        self.setIndentation(10)
        self.setUniformRowHeights(True)

        self.clicked.connect(self.one_clicked)

    def one_clicked(self, index):
        path = self.c_model.filePath(index)
        if path != self.main_win_item.abs_current_dir:
            self.setCurrentIndex(index)
            self.new_history_item.emit(path)
            self.load_st_grid_sig.emit(path)

    def expand_path(self, root: str):
        if root.startswith(os.path.expanduser("~")):
            root = os.path.join(self.macintosh, root.lstrip(os.sep))

        index = self.c_model.index(root)
        self.setCurrentIndex(index)
        self.expand(index)
        self.scrollTo(
            index,
            QAbstractItemView.ScrollHint.EnsureVisible
        )

    def remove_fav_cmd(self, path: str):
        item = NameUrlItem(
            name=os.path.basename(path),
            url=path
        )
        self.remove_fav.emit(item)

    def add_fav_cmd(self, path: str):
        item = NameUrlItem(
            name=os.path.basename(path),
            url=path
        )
        self.add_fav.emit(item)

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return

        context_menu = UMenu(parent=self)
        context_actions = Actions(context_menu)
        src = self.c_model.filePath(index)
        index = self.c_model.index(src)
        context_menu.add_action(
            action=context_actions.open_thumb,
            callback=lambda: self.one_clicked(index)
        )
        context_menu.add_action(
            action=context_actions.new_main_win,
            callback=lambda: self.new_main_win.emit(src)
        )
        if src in JsonData.favs:
            context_menu.add_action(
                action=context_actions.fav_remove,
                callback=lambda: self.remove_fav_cmd(src)
            )
        else:
            context_menu.add_action(
                action=context_actions.fav_add,
                callback=lambda: self.add_fav_cmd(src)
            )
        context_menu.addSeparator()
        context_menu.add_action(
            action=context_actions.reveal,
            callback=lambda: self.reveal.emit([src, ])
        )
        context_menu.addSeparator()
        context_menu.add_action(
            action=context_actions.copy_name,
            callback=lambda: self.copy_names.emit([src, ])
        )
        context_menu.add_action(
            action=context_actions.copy_path,
            callback=lambda: self.copy_urls.emit([src, ])
        )
        context_menu.show_under_mouse()
