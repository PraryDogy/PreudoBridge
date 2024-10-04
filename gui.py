import json
import os
import subprocess

from PyQt5.QtCore import QEvent, QObject, Qt, QTimer
from PyQt5.QtGui import QCloseEvent, QColor, QKeyEvent, QResizeEvent
from PyQt5.QtWidgets import (QApplication, QGraphicsDropShadowEffect,
                             QHBoxLayout, QLabel, QSplitter, QTabWidget,
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
        self.folders_tree_wid.folders_tree_clicked.connect(self.open_folder_cmd)
        self.folders_tree_wid.add_to_favs_clicked.connect(self.add_fav_cmd)
        self.folders_tree_wid.del_favs_clicked.connect(self.del_fav_cmd)
        self.tabs_wid.addTab(self.folders_tree_wid, "Папки")

        self.folders_fav_wid = TreeFavorites()
        self.folders_fav_wid.on_fav_clicked.connect(self.open_folder_cmd)
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
        self.top_bar.back_sig.connect(self.next_back_cmd)
        self.top_bar.next_sig.connect(self.next_back_cmd)

        self.r_lay.addWidget(self.top_bar)

        self.resize_timer = QTimer(parent=self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(lambda: self.grid.rearrange(self.get_grid_width()))

        root = Config.json_data["root"]

        self.setWindowTitle(Config.json_data["root"])
        self.folders_tree_wid.expand_path(root)
        self.load_standart_grid()


        self.back_up_btns = QWidget(parent=self)
        self.back_up_btns.setFixedSize(140, 40)
        self.back_up_btns.move(self.width() // 2, self.height() - 70)
        self.back_up_btns.setObjectName("back_up")
        self.back_up_btns.show()

        self.back_up_btns.setStyleSheet(
            """
            #back_up {
            background-color: rgba(128, 128, 128, 0.40);
            border-radius: 15px;
            }
            """
            )

        back_up_lay = QHBoxLayout()
        self.back_up_btns.setLayout(back_up_lay)

        back_btn = QLabel("Назад")
        back_btn.setGraphicsEffect(self.get_shadow())
        back_btn.mouseReleaseEvent = lambda e: self.open_folder_cmd(os.path.split(Config.json_data["root"])[0])
        back_up_lay.addWidget(back_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        up_btn = QLabel("Наверх")
        up_btn.setGraphicsEffect(self.get_shadow())
        up_btn.mouseReleaseEvent = lambda e: self.grid.verticalScrollBar().setValue(0)
        back_up_lay.addWidget(up_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def get_shadow(self):
        effect = QGraphicsDropShadowEffect()
        effect.setOffset(0, 0)
        effect.setColor(QColor(0, 0, 0, 200))
        effect.setBlurRadius(15)
        return effect

    def open_folder_cmd(self, root: str):
        Config.json_data["root"] = root
        self.top_bar.update_history()
        self.folders_tree_wid.expand_path(Config.json_data["root"])
        self.setWindowTitle(root)
        self.load_standart_grid()

    def next_back_cmd(self, root: str):
        Config.json_data["root"] = root
        self.folders_tree_wid.expand_path(root)
        self.setWindowTitle(root)
        self.load_standart_grid()

    def add_fav_cmd(self, root: str):
        name = os.path.basename(root)
        self.folders_fav_wid.add_item(name, root)
        Config.json_data["favs"][root] = name

    def del_fav_cmd(self, root: str):
        self.folders_fav_wid.del_item(root)

    def open_path_btn_cmd(self, path: str):
        if not os.path.exists(path):
            return

        filepath = ""
        if os.path.isfile(path):
            if path.endswith(Config.img_ext):
                filepath = path
            path, _ = os.path.split(path)

        Config.json_data["root"] = path
        self.top_bar.update_history()
        self.folders_tree_wid.expand_path(path)
        self.setWindowTitle(path)
        self.load_standart_grid()
        QTimer.singleShot(1500, lambda: self.grid.move_to_wid(filepath))

    def disable_top_bar_btns(self, b: bool):
        self.back_up_btns.setDisabled(b)
        self.top_bar.open_btn.setDisabled(b)
        self.top_bar.sort_vozrast_button.setDisabled(b)
        self.top_bar.sort_widget.setDisabled(b)

    def load_search_grid(self, search_text: str):
        self.disable_top_bar_btns(True)

        if self.grid:
            self.grid.close()

        ww = self.get_grid_width()
        self.grid = GridSearch(width=ww, search_text=search_text)
        self.grid.finished.connect(lambda: self.setWindowTitle(f"🟢\tРезультаты поиска: \"{search_text}\""))
        self.grid.show_in_folder.connect(self.search_grid_show_in_folder)
        self.setWindowTitle(f"🟠\tИдет поиск: \"{search_text}\"")
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
        self.grid: GridStandart
        self.grid.add_fav_sig.connect(self.add_fav_cmd)
        self.grid.del_fav_sig.connect(self.del_fav_cmd)
        self.grid.open_folder_sig.connect(self.open_folder_cmd)
        self.r_lay.addWidget(self.grid)

    def get_grid_width(self):
        return Config.json_data["ww"] - self.tabs_wid.width() - 180

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        Config.json_data["ww"] = self.geometry().width()
        Config.json_data["hh"] = self.geometry().height()
        self.back_up_btns.move(self.width() // 2, self.height() - 70)
        self.resize_timer.stop()
        self.resize_timer.start(500)
        # return super().resizeEvent(a0)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self.hide()
        self.grid.stop_and_wait_threads()
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
