import subprocess

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QDragMoveEvent, QDropEvent, QMouseEvent
from PyQt5.QtWidgets import (QAction, QLabel, QListWidget, QListWidgetItem,
                             QMenu)

from cfg import Config
from utils import Utils


class FavItem(QLabel):
    _on_fav_clicked = pyqtSignal()
    _del_clicked = pyqtSignal()

    def __init__(self, name: str, src: str):
        super().__init__(text=name)
        self.name = name
        self.src = src

        self.setFixedHeight(25)

        self.list_item = QListWidgetItem()
        self.list_item.setSizeHint(self.sizeHint())

        self.context_menu = QMenu(self)

        view_ac = QAction("Просмотр", self)
        view_ac.triggered.connect(lambda: self._on_fav_clicked.emit())
        self.context_menu.addAction(view_ac)

        open_finder_action = QAction("Показать в Finder", self)
        open_finder_action.triggered.connect(lambda: self.open_in_finder(src))
        self.context_menu.addAction(open_finder_action)

        self.context_menu.addSeparator()

        copy_path_action = QAction("Скопировать путь до папки", self)
        copy_path_action.triggered.connect(lambda: Utils.copy_path(src))
        self.context_menu.addAction(copy_path_action)

        self.context_menu.addSeparator()

        fav_action = QAction("Удалить из избранного", self)
        fav_action.triggered.connect(lambda: self._del_clicked.emit())
        self.context_menu.addAction(fav_action)

        self.setContentsMargins(10, 0, 10, 0)

    def mouseReleaseEvent(self, ev: QMouseEvent | None) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self._on_fav_clicked.emit()

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:
        self.context_menu.exec_(ev.globalPos())

    def open_in_finder(self, path: str):
        subprocess.call(["open", "-R", path])


class TreeFavorites(QListWidget):
    on_fav_clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.init_ui()

    def init_ui(self):
        favs: dict = Config.json_data["favs"]
        for src, name in favs.items():
            self.add_item(name, src)

    def add_item(self, name: str, src: str):
        item = FavItem(name, src)
        item._del_clicked.connect(lambda: self.del_item(src))
        item._on_fav_clicked.connect(lambda: self.on_fav_clicked.emit(src))
        self.addItem(item.list_item)
        self.setItemWidget(item.list_item, item)

    def del_item(self, src: str):
        favs: dict = Config.json_data.get("favs")
        favs.pop(src)
        self.clear()
        self.init_ui()
    
    def dropEvent(self, event: QDropEvent | None) -> None:
        super().dropEvent(event)
        new_order = {}
        for i in range(self.count()):
            item = self.item(i)
            fav_widget = self.itemWidget(item)
            if isinstance(fav_widget, FavItem):
                new_order[fav_widget.src] = fav_widget.name

        Config.json_data["favs"] = new_order

        # return super().dropEvent(event)