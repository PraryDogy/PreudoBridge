import os
import subprocess

from PyQt5.QtCore import QDir, QModelIndex, Qt, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent
from PyQt5.QtWidgets import (QAction, QFileSystemModel, QLabel, QListView,
                             QMenu, QSizePolicy, QSpacerItem, QTreeView,
                             QVBoxLayout, QWidget, QListWidget)

from cfg import Config
from utils import Utils


class TreeFolders(QTreeView):
    folders_tree_clicked = pyqtSignal(str)
    add_to_favs_clicked = pyqtSignal(str)
    del_favs_clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()

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
        self.folders_tree_clicked.emit(path)

        if self.isExpanded(index):
            self.collapse(index)
        else:
            self.expand(index)

    def expand_path(self, root: str):
        index = self.c_model.index(root)
        self.setCurrentIndex(index)
        self.expand(index)

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return

        menu = QMenu(self)
        src = self.c_model.filePath(index)
        index = self.c_model.index(src)

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

        menu.exec_(self.mapToGlobal(event.pos()))

    def open_in_finder(self, path: str):
        subprocess.call(["open", "-R", path])



class TreeFolders(QListView):
    folders_tree_clicked = pyqtSignal(str)
    add_to_favs_clicked = pyqtSignal(str)
    del_favs_clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("trees")
        self.c_model = QFileSystemModel()
        self.c_model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot)
        self.c_model.setRootPath('/Volumes')
        self.setModel(self.c_model)
        self.setRootIndex(self.c_model.index("/Volumes"))

        self.doubleClicked.connect(self.on_double_click)
        self.setContentsMargins(0, 20, 0, 0)

        # self.setStyleSheet("#trees {padding-top: 20px;}")

        self.back_btn = QLabel(parent=self, text="\u25C0   Назад")
        self.back_btn.setFixedSize(self.width(), 20)
        self.back_btn.setStyleSheet("padding-left: 5px;")
        self.back_btn.move(self.x(), self.y())
        self.back_btn.mouseDoubleClickEvent = self.back_click

    def back_click(self, e):
        root = os.path.dirname(Config.json_data["root"])
        self.expand_path(root)
        self.folders_tree_clicked.emit(root)

    def on_double_click(self, index: QModelIndex):
        path = self.c_model.filePath(index)
        self.expand_path(path)
        self.folders_tree_clicked.emit(path)
    
    def expand_path(self, path: str):
        self.setRootIndex(self.c_model.index(path))

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return

        menu = QMenu(self)
        src = self.c_model.filePath(index)
        index = self.c_model.index(src)

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

        menu.exec_(self.mapToGlobal(event.pos()))

    def open_in_finder(self, path: str):
        subprocess.call(["open", "-R", path])



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
        self.back_btn.setFixedHeight(30)
        self.back_btn.addItem("Назад")
        self.back_btn.itemDoubleClicked.connect(self.back_click)
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

    def back_click(self, e):
        print(e)
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