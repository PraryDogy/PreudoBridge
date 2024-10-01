import json
import os
import subprocess

from PyQt5.QtCore import QDir, QEvent, QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QKeyEvent, QResizeEvent
from PyQt5.QtWidgets import (QAction, QApplication, QFileSystemModel, QFrame,
                             QLabel, QMenu, QSplitter, QTabWidget, QTreeView,
                             QVBoxLayout, QWidget)

from cfg import Config
from utils import Utils
from widgets.grid_standart import GridStandart
from widgets.top_bar import TopBarWidget


class TreeWidget(QTreeView):
    folders_tree_clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        self.model = QFileSystemModel()
        self.model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot)
        self.model.setRootPath("/Volumes")
        self.setModel(self.model)
        self.setRootIndex(self.model.index("/Volumes"))

        self.setHeaderHidden(True)
        for i in range(1, self.model.columnCount()):
            self.setColumnHidden(i, True)

        self.setIndentation(10)
        self.setUniformRowHeights(True)

        self.clicked.connect(self.one_clicked)

    def one_clicked(self, index):
        path = self.model.filePath(index)
        self.setCurrentIndex(index)
        self.folders_tree_clicked.emit(path)

        if self.isExpanded(index):
            self.collapse(index)
        else:
            self.expand(index)

    def expand_path(self, root: str):
        index = self.model.index(root)
        self.setCurrentIndex(index)
        self.expand(index)

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return

        menu = QMenu(self)
        file_path = self.model.filePath(index)
        index = self.model.index(file_path)

        open_finder_action = QAction("Просмотр", self)
        open_finder_action.triggered.connect(lambda: self.one_clicked(index))
        menu.addAction(open_finder_action)

        menu.addSeparator()

        open_finder_action = QAction("Показать в Finder", self)
        open_finder_action.triggered.connect(lambda: self.open_in_finder(file_path))
        menu.addAction(open_finder_action)

        copy_path_action = QAction("Скопировать путь до папки", self)
        copy_path_action.triggered.connect(lambda: Utils.copy_path(file_path))
        menu.addAction(copy_path_action)

        menu.exec_(self.mapToGlobal(event.pos()))

    def open_in_finder(self, path: str):
        subprocess.call(["open", "-R", path])


class SimpleFileExplorer(QWidget):
    def __init__(self):
        super().__init__()

        self.clmn_count = 1
        self.finder_items = []
        self.finder_images: dict = {}
        self.grid: GridStandart = None

        ww, hh = Config.json_data["ww"], Config.json_data["hh"]
        self.resize(ww, hh)
        self.move_to_filepath: str = None

        main_lay = QVBoxLayout()
        main_lay.setContentsMargins(5, 5, 5, 5)
        main_lay.setSpacing(0)
        self.setLayout(main_lay)

        splitter_wid = QSplitter(Qt.Horizontal)
        splitter_wid.splitterMoved.connect(self.resizeEvent)
        main_lay.addWidget(splitter_wid)

        self.left_wid = QTabWidget()
        splitter_wid.addWidget(self.left_wid)
        splitter_wid.setStretchFactor(0, 0)
        
        self.folders_tree_wid = TreeWidget()
        self.folders_tree_wid.folders_tree_clicked.connect(self.on_files_tree_clicked)
        self.left_wid.addTab(self.folders_tree_wid, "Папки")
        self.left_wid.addTab(QLabel("Тут будут каталоги"), "Каталог")

        right_wid = QWidget()
        splitter_wid.addWidget(right_wid)
        splitter_wid.setStretchFactor(1, 1)

        self.r_lay = QVBoxLayout()
        self.r_lay.setContentsMargins(0, 0, 0, 0)
        self.r_lay.setSpacing(0)
        right_wid.setLayout(self.r_lay)
        
        self.top_bar = TopBarWidget()
        self.top_bar.sort_btn_press.connect(self.load_standart_grid)
        self.top_bar.level_up_btn_press.connect(self.level_up_btn_cmd)
        self.top_bar.open_path_btn_press.connect(self.open_path_btn_cmd)
        self.r_lay.addWidget(self.top_bar)

        self.resize_timer = QTimer(parent=self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.setInterval(500)
        self.resize_timer.timeout.connect(self.load_standart_grid)

        root = Config.json_data["root"]

        if root and os.path.exists(root):
            self.setWindowTitle(Config.json_data["root"])
            self.folders_tree_wid.expand_path(root)
            self.load_standart_grid()

        else:
            self.setWindowTitle("Ошибка")
            self.grid = QLabel("Такой папки не существует. \n Проверьте подключение к сетевому диску")
            self.r_lay.addWidget(self.grid)

    def on_files_tree_clicked(self, root: str):
        Config.json_data["root"] = root
        self.setWindowTitle(root)
        self.load_standart_grid()

    def open_path_btn_cmd(self, path: str):
        if not os.path.exists(path):
            return

        if os.path.isfile(path):
            if path.endswith(Config.img_ext):
                self.move_to_filepath = path
            path, _ = os.path.split(path)

        Config.json_data["root"] = path
        self.folders_tree_wid.expand_path(path)
        self.setWindowTitle(path)
        self.load_standart_grid()

    def level_up_btn_cmd(self):
        path = os.path.dirname(Config.json_data["root"])
        Config.json_data["root"] = path

        self.folders_tree_wid.expand_path(path)
        self.setWindowTitle(Config.json_data["root"])
        self.load_standart_grid()

    def load_standart_grid(self):
        self.top_bar.level_up_button.setDisabled(False)

        if self.grid:
            self.grid.close()

        ww = self.get_grid_width()
        self.grid = GridStandart(width=ww)
        self.r_lay.addWidget(self.grid)

    def get_grid_width(self):
        return Config.json_data["ww"] - self.left_wid.width() - 180

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        Config.json_data["ww"] = self.geometry().width()
        Config.json_data["hh"] = self.geometry().height()
        self.resize_timer.stop()
        self.resize_timer.start()
        # return super().resizeEvent(a0)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self.hide()
        a0.ignore()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Up:
            if a0.modifiers() == Qt.KeyboardModifier.MetaModifier:
                self.level_up_btn_cmd()

        elif a0.key() == Qt.Key.Key_W:
            if a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.hide()

        elif a0.key() == Qt.Key.Key_Q:
            if a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
                QApplication.instance().quit()


class CustomApp(QApplication):
    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.aboutToQuit.connect(self.on_exit)
        self.installEventFilter(self)

    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if a1.type() == QEvent.Type.ApplicationActivate:
            Utils.get_main_win().show()
        return False

    def on_exit(self):
        with open(Config.json_file, 'w') as f:
            json.dump(Config.json_data, f, indent=4, ensure_ascii=False)
