import json
import os
import subprocess

from PyQt5.QtCore import QDir, QEvent, QObject, Qt, QTimer
from PyQt5.QtGui import QCloseEvent, QKeyEvent, QResizeEvent
from PyQt5.QtWidgets import (QApplication, QLabel, QSplitter, QTabWidget,
                             QVBoxLayout, QWidget)

from cfg import Config
from utils import Utils
from widgets.grid_search import GridSearch
from widgets.grid_standart import GridStandart
from widgets.top_bar import TopBar
from widgets.tree_favorites import TreeFavorites
from widgets.tree_folders import TreeFolders


class SimpleFileExplorer(QWidget):
    def __init__(self):
        super().__init__()

        self.dots_count = 1
        self.clmn_count = 1
        self.finder_items = []
        self.finder_images: dict = {}
        self.grid: GridStandart = None

        ww, hh = Config.json_data["ww"], Config.json_data["hh"]
        self.resize(ww, hh)

        main_lay = QVBoxLayout()
        main_lay.setContentsMargins(5, 5, 5, 5)
        main_lay.setSpacing(0)
        self.setLayout(main_lay)

        splitter_wid = QSplitter(Qt.Horizontal)
        splitter_wid.splitterMoved.connect(self.resizeEvent)
        main_lay.addWidget(splitter_wid)

        self.tabs_wid = QTabWidget()
        splitter_wid.addWidget(self.tabs_wid)
        splitter_wid.setStretchFactor(0, 0)
        
        self.folders_tree_wid = TreeFolders()
        self.folders_tree_wid.folders_tree_clicked.connect(self.on_files_tree_clicked_cmd)
        self.folders_tree_wid.add_to_favs_clicked.connect(self.add_fav_cmd)
        self.folders_tree_wid.del_favs_clicked.connect(self.del_fav_cmd)
        self.tabs_wid.addTab(self.folders_tree_wid, "Папки")

        self.folders_fav_wid = TreeFavorites()
        self.folders_fav_wid.on_fav_clicked.connect(self.on_fav_tree_clicked_cmd)
        self.tabs_wid.addTab(self.folders_fav_wid, "Избранное")

        self.tabs_wid.addTab(QLabel("Тут будут каталоги"), "Каталог")

        right_wid = QWidget()
        splitter_wid.addWidget(right_wid)
        splitter_wid.setStretchFactor(1, 1)

        self.r_lay = QVBoxLayout()
        self.r_lay.setContentsMargins(0, 0, 0, 0)
        self.r_lay.setSpacing(0)
        right_wid.setLayout(self.r_lay)
        
        self.top_bar = TopBar()

        # У ТЕБЯ СОРТИРОВКА ТОЛЬКО СТАНДАРТНУЮ СЕТКУ ЗАГРУЖАЕТ КАК И РЕСАЙЗ МЕТОД
        # НАПИШИ МЕТОД КОТОРЫЙ ПРОСТО ПЕРЕРАСПРЕДЕЛЯЕТ ВИДЖЕТЫ В СЕТКЕ
        self.top_bar.sort_vozrast_btn_press.connect(self.load_standart_grid)
        self.top_bar.open_path_btn_press.connect(self.open_path_btn_cmd)
        self.top_bar.search_wid.start_search_sig.connect(self.load_search_grid)
        self.top_bar.search_wid.stop_search_sig.connect(self.load_standart_grid)

        self.r_lay.addWidget(self.top_bar)

        self.resize_timer = QTimer(parent=self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(lambda: self.grid.rearrange(self.get_grid_width()))

        root = Config.json_data["root"]

        self.setWindowTitle(Config.json_data["root"])
        self.folders_tree_wid.expand_path(root)
        self.load_standart_grid()
        
    def on_files_tree_clicked_cmd(self, root: str):
        Config.json_data["root"] = root
        self.setWindowTitle(root)
        self.load_standart_grid()

    def add_fav_cmd(self, root: str):
        name = os.path.basename(root)
        self.folders_fav_wid.add_item(name, root)
        Config.json_data["favs"][root] = name

    def del_fav_cmd(self, root: str):
        self.folders_fav_wid.del_item(root)

    def on_fav_tree_clicked_cmd(self, root: str):
        Config.json_data["root"] = root
        self.setWindowTitle(root)
        self.folders_tree_wid.expand_path(Config.json_data["root"])
        self.load_standart_grid()

    def open_path_btn_cmd(self, path: str):
        if not os.path.exists(path):
            return

        filepath = ""
        if os.path.isfile(path):
            if path.endswith(Config.img_ext):
                filepath = path
            path, _ = os.path.split(path)

        Config.json_data["root"] = path
        self.folders_tree_wid.expand_path(path)
        self.setWindowTitle(path)
        self.load_standart_grid()
        QTimer.singleShot(1500, lambda: self.grid.move_to_wid(filepath))

    def disable_top_bar_btns(self, b: bool):
        self.top_bar.open_btn.setDisabled(b)
        self.top_bar.sort_vozrast_button.setDisabled(b)
        self.top_bar.sort_widget.setDisabled(b)

    def load_search_grid(self, search_text: str):
        self.disable_top_bar_btns(True)

        if self.grid:
            self.grid.close()

        ww = self.get_grid_width()
        self.grid = GridSearch(width=ww, search_text=search_text)
        self.grid.finished.connect(lambda: self.setWindowTitle(f"🟢\tРезультаты поиска: {search_text}"))
        self.grid.show_in_folder.connect(self.search_grid_show_in_folder)
        self.setWindowTitle(f"🟠\tИдет поиск: {search_text}")
        self.r_lay.addWidget(self.grid)

    def search_grid_show_in_folder(self, src: str):
        root = os.path.dirname(src)
        Config.json_data["root"] = root
        self.folders_tree_wid.expand_path(root)
        self.setWindowTitle(Config.json_data["root"])
        self.load_standart_grid()
        QTimer.singleShot(1500, lambda: self.grid.move_to_wid(src))

    def load_standart_grid(self):
        self.disable_top_bar_btns(False)
        self.top_bar.search_wid.clear_search_sig.emit()

        if self.grid:
            self.grid.close()

        self.setWindowTitle(Config.json_data["root"])
        ww = self.get_grid_width()
        self.grid = GridStandart(width=ww)
        self.r_lay.addWidget(self.grid)

    def get_grid_width(self):
        return Config.json_data["ww"] - self.tabs_wid.width() - 180

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        Config.json_data["ww"] = self.geometry().width()
        Config.json_data["hh"] = self.geometry().height()
        self.resize_timer.stop()
        self.resize_timer.start(500)
        return super().resizeEvent(a0)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self.hide()
        a0.ignore()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_W:
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
