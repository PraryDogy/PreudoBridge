import os
import subprocess

from PyQt5.QtCore import QDir, QModelIndex, pyqtSignal, Qt
from PyQt5.QtGui import QContextMenuEvent
from PyQt5.QtWidgets import (QAction, QFileSystemModel, QLabel, QListView,
                             QListWidget, QListWidgetItem, QMenu, QVBoxLayout,
                             QWidget)

from cfg import Config
from utils import Utils


class TreeFolders(QWidget):
    folders_tree_clicked = pyqtSignal(str)
    add_to_favs_clicked = pyqtSignal(str)
    del_favs_clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

        self.back_btn = QListWidget()
        self.back_btn.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.back_btn.setFixedHeight(27)
        self.add_item()
        layout.addWidget(self.back_btn)

        self.c_model = QFileSystemModel()
        self.c_model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot)
        self.c_model.setRootPath('/Volumes')

        self.list_view = QListView()
        self.list_view.setModel(self.c_model)
        self.list_view.setRootIndex(self.c_model.index("/Volumes"))
        layout.addWidget(self.list_view)

        self.list_view.doubleClicked.connect(self.on_double_click)
        self.list_view.contextMenuEvent = self.custom_context

    def add_item(self):
        wid = QLabel(text="Назад")
        wid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wid.setFixedHeight(25)
        list_item = QListWidgetItem()
        list_item.setSizeHint(wid.sizeHint())

        self.back_btn.addItem(list_item)
        self.back_btn.setItemWidget(list_item, wid)

        wid.mouseDoubleClickEvent = self.back_click

    def back_click(self, e):
        root = os.path.dirname(Config.json_data["root"])
        self.expand_path(root)
        self.folders_tree_clicked.emit(root)

    def on_double_click(self, index: QModelIndex):
        path = self.c_model.filePath(index)
        self.expand_path(path)
        self.folders_tree_clicked.emit(path)
    
    def expand_path(self, path: str):
        self.list_view.setRootIndex(self.c_model.index(path))

    def custom_context(self, event: QContextMenuEvent) -> None:
        index = self.list_view.indexAt(event.pos())
        if not index.isValid():
            return

        # Получаем глобальную позицию меню
        global_pos = self.list_view.mapToGlobal(event.pos())

        menu = QMenu(self)
        src = self.c_model.filePath(index)

        open_finder_action = QAction("Просмотр", self)
        open_finder_action.triggered.connect(lambda: self.one_clicked(index))
        menu.addAction(open_finder_action)

        menu.addSeparator()

        open_finder_action = QAction("Показать в Finder", self)
        open_finder_action.triggered.connect(lambda: self.open_in_finder(src))
        menu.addAction(open_finder_action)

        copy_path_action = QAction("Скопировать путь до папки", self)
        copy_path_action.triggered.connect(lambda: Utils.copy_path(src))
        menu.addAction(copy_path_action)

        menu.addSeparator()

        favs = Config.json_data["favs"]
        if src in favs:
            fav_action = QAction("Удалить из избранного", self)
            fav_action.triggered.connect(lambda: self.del_favs_clicked.emit(src))
            menu.addAction(fav_action)
        else:
            fav_action = QAction("Добавить в избранное", self)
            fav_action.triggered.connect(lambda: self.add_to_favs_clicked.emit(src))
            menu.addAction(fav_action)

        # Показываем меню в правильной глобальной позиции
        menu.exec_(global_pos)

    def open_in_finder(self, path: str):
        subprocess.call(["open", "-R", path])