import os
import subprocess

from PyQt5.QtCore import QDir, Qt, pyqtSignal
from PyQt5.QtWidgets import (QAction, QFileSystemModel, QLabel, QListWidget,
                             QListWidgetItem, QMenu, QTreeView)
from PyQt5.QtGui import QContextMenuEvent, QMouseEvent
from cfg import Config
from utils import Utils


class TreeFavorites(QListWidget):
    on_fav_clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        mac = "/Volumes/Macintosh HD"
        desktop = mac + os.path.join(os.path.expanduser('~'), 'Desktop')
        downloads = mac + os.path.join(os.path.expanduser('~'), 'Downloads')
        self._add_def_item("Рабочий стол", desktop)
        self._add_def_item("Загрузки", downloads)
        self.fav_items: dict = {}

        favs: dict = Config.json_data["favs"]
        for src, name in favs.items():
            self.add_item(name, src)

    def _add_def_item(self, name: str, src: str):
        wid = QLabel(text=name)
        wid.setStyleSheet("padding-left: 5px;")
        wid.setFixedHeight(25)
        list_item = QListWidgetItem()
        list_item.setSizeHint(wid.sizeHint())

        self.addItem(list_item)
        self.setItemWidget(list_item, wid)

        wid.mouseReleaseEvent = lambda e: self.l_click(e, src)

    def add_item(self, name: str, src: str):
        wid = QLabel(text=name)
        wid.setStyleSheet("padding-left: 5px;")
        wid.setFixedHeight(25)
        list_item = QListWidgetItem()
        list_item.setSizeHint(wid.sizeHint())

        self.addItem(list_item)
        self.setItemWidget(list_item, wid)

        self.fav_items[src] = wid

        wid.mouseReleaseEvent = lambda e: self.l_click(e, src)
        wid.contextMenuEvent = lambda e: self.custom_context(e, src)

    def del_item(self, src: str):
        self.fav_items[src].deleteLater()
        favs: dict = Config.json_data["favs"]
        favs.pop(src)

    def l_click(self, e: QMouseEvent | None, src) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.on_fav_clicked.emit(src)
        return super().mouseReleaseEvent(e)

    def custom_context(self, a0: QContextMenuEvent | None, src: str) -> None:
        menu = QMenu(self)

        view_ac = QAction("Просмотр", self)
        view_ac.triggered.connect(lambda: self.on_fav_clicked.emit(src))
        menu.addAction(view_ac)

        open_finder_action = QAction("Показать в Finder", self)
        open_finder_action.triggered.connect(lambda: self.open_in_finder(src))
        menu.addAction(open_finder_action)

        menu.addSeparator()

        copy_path_action = QAction("Скопировать путь до папки", self)
        copy_path_action.triggered.connect(lambda: Utils.copy_path(src))
        menu.addAction(copy_path_action)

        menu.addSeparator()

        fav_action = QAction("Удалить из избранного", self)
        fav_action.triggered.connect(lambda: self.del_item(src))
        menu.addAction(fav_action)

        menu.exec_(a0.globalPos())

    def open_in_finder(self, path: str):
        subprocess.call(["open", "-R", path])