import os
import subprocess

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import (QContextMenuEvent, QDragEnterEvent, QDragLeaveEvent,
                         QDropEvent, QMouseEvent)
from PyQt5.QtWidgets import (QAction, QLabel, QListWidget, QListWidgetItem,
                             QMenu)

from cfg import JsonData
from signals import SignalsApp
from utils import Utils

from .win_rename import WinRename


class FavItem(QLabel):
    del_click = pyqtSignal()
    rename_finished = pyqtSignal(str)

    def __init__(self, name: str, src: str):
        super().__init__(text=name)
        self.name = name
        self.src = src
        self.setFixedHeight(25)

        self.context_menu = QMenu(self)

        view_ac = QAction("Просмотр", self)
        view_ac.triggered.connect(lambda: SignalsApp.all.load_standart_grid.emit(self.src))
        self.context_menu.addAction(view_ac)

        open_finder_action = QAction("Показать в Finder", self)
        open_finder_action.triggered.connect(lambda: self.open_in_finder(src))
        self.context_menu.addAction(open_finder_action)

        self.context_menu.addSeparator()

        copy_path_action = QAction("Скопировать путь до папки", self)
        copy_path_action.triggered.connect(lambda: Utils.copy_path(src))
        self.context_menu.addAction(copy_path_action)

        self.context_menu.addSeparator()

        rename_action = QAction("Переименовать", self)
        rename_action.triggered.connect(self.rename_cmd)
        self.context_menu.addAction(rename_action)

        fav_action = QAction("Удалить", self)
        fav_action.triggered.connect(lambda: self.del_click.emit())
        self.context_menu.addAction(fav_action)

        self.setContentsMargins(10, 0, 10, 0)

    def open_in_finder(self, path: str):
        subprocess.call(["open", "-R", path])

    def rename_cmd(self):
        self.win = WinRename(self.name)
        self.win._finished.connect(self.rename_finished_cmd)
        Utils.center_win(Utils.get_main_win(), self.win)
        self.win.show()

    def rename_finished_cmd(self, text: str):
        self.setText(text)
        self.rename_finished.emit(text)
        JsonData.write_config()

    def mouseReleaseEvent(self, ev: QMouseEvent | None) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            SignalsApp.all.new_history.emit(self.src)
            SignalsApp.all.load_standart_grid.emit(self.src)

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:
        self.context_menu.exec_(ev.globalPos())


class TreeFavorites(QListWidget):
    def __init__(self):
        super().__init__()
        SignalsApp.all.add_fav.connect(self.add_fav_cmd)
        SignalsApp.all.del_fav.connect(self.del_item)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setAcceptDrops(True)
        self.init_ui()

    def init_ui(self):
        for src, name in JsonData.favs.items():
            item = self.add_widget_item(name, src)

            if JsonData.root == src:
                self.setCurrentItem(item)

    def add_fav_cmd(self, root: str):
        if root not in JsonData.favs:
            name = os.path.basename(root)
            JsonData.favs[root] = name
            self.add_widget_item(name, root)

    def add_widget_item(self, name: str, root: str) -> QListWidgetItem:
        item = FavItem(name, root)
        item.del_click.connect(lambda: self.del_item(root))
        item.rename_finished.connect(lambda new_name: self.update_name(root, new_name))

        list_item = QListWidgetItem()
        list_item.setSizeHint(item.sizeHint())

        self.addItem(list_item)
        self.setItemWidget(list_item, item)

        return list_item

    def update_name(self, src: str, new_name: str):
        if src in JsonData.favs:
            JsonData.favs[src] = new_name

    def del_item(self, src: str):
        print(src)
        return
        JsonData.favs.pop(src)
        self.clear()
        self.init_ui()
    
    def dropEvent(self, a0: QDropEvent | None) -> None:
        urls = a0.mimeData().urls()
        if urls:
            root = os.sep + urls[0].toLocalFile().strip(os.sep)
            if os.path.isdir(root):
                self.add_fav_cmd(root)

        else:
            super().dropEvent(a0)
            new_order = {}

            for i in range(self.count()):
                item = self.item(i)
                fav_widget = self.itemWidget(item)
                if isinstance(fav_widget, FavItem):
                    new_order[fav_widget.src] = fav_widget.name

            JsonData.favs = new_order
    
    def dragEnterEvent(self, a0: QDragEnterEvent | None) -> None:
        if a0.mimeData().hasUrls():
            a0.acceptProposedAction()
        return super().dragEnterEvent(a0)
    
    def dragLeaveEvent(self, a0: QDragLeaveEvent | None) -> None:
        return super().dragLeaveEvent(a0)

    def mouseReleaseEvent(self, e: QMouseEvent | None) -> None:
        curr = self.currentItem()
        if isinstance(curr, QListWidgetItem):
            curr.setSelected(False)