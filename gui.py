import json
import os
from typing import Union

from PyQt5.QtCore import QEvent, QObject, Qt, QTimer
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

        self.grid: Union[GridSearch, GridStandart] = None

        ww, hh = Config.json_data.get("ww"), Config.json_data.get("hh")
        self.resize(ww, hh)

        self.resize_timer = QTimer(parent=self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(lambda: self.grid.resize_grid(self.get_grid_width()))

        self.migaet_timer = QTimer(parent=self)
        self.migaet_timer.timeout.connect(self.grid_search_migaet_title)

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
        self.folders_tree_wid.folders_tree_clicked.connect(self.tree_wid_view_folder_cmd)
        self.folders_tree_wid.add_to_favs_clicked.connect(self.tree_wid_add_fav_cmd)
        self.folders_tree_wid.del_favs_clicked.connect(self.tree_wid_del_fav_cmd)
        self.tabs_wid.addTab(self.folders_tree_wid, "Папки")

        self.folders_fav_wid = TreeFavorites()
        self.folders_fav_wid.on_fav_clicked.connect(self.tree_wid_view_folder_cmd)
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

        self.top_bar.sort_widget.sort_click.connect(self.top_bar_sort_grid)
        self.top_bar.go_btn.open_path.connect(self.top_bar_open_path_btn_cmd)
        self.top_bar.search_wid.start_search_sig.connect(self.grid_search_load)
        self.top_bar.search_wid.stop_search_sig.connect(self.grid_standart_load)

        self.top_bar.level_up_sig.connect(self.grid_standart_load)
        self.top_bar.back_sig.connect(self.top_bar_next_back_cmd)
        self.top_bar.next_sig.connect(self.top_bar_next_back_cmd)

        self.r_lay.addWidget(self.top_bar)

        self.grid_standart_load()

        self.scroll_up = QLabel(parent=self, text="\u25B2")
        self.scroll_up.hide()
        self.scroll_up.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_up.mouseReleaseEvent = lambda e: self.grid.verticalScrollBar().setValue(0)
        self.scroll_up.setFixedSize(40, 40)
        self.scroll_up.move(self.width() - 70, self.height() - 70)
        self.scroll_up.setStyleSheet(
            """
            background-color: rgba(128, 128, 128, 0.40);
            border-radius: 20px;
            """
            )

    def top_bar_sort_grid(self):
        if isinstance(self.grid, GridSearch):
            self.grid.sort_grid(self.get_grid_width())

        elif isinstance(self.grid, GridStandart):
            self.grid_standart_load()

    def top_bar_setDisabled(self, b: bool):
        self.top_bar.back.setDisabled(b)
        self.top_bar.next.setDisabled(b)
        self.top_bar.level_up_btn.setDisabled(b)
        self.top_bar.go_btn.setDisabled(b)
        self.top_bar.sort_widget.setDisabled(b)
        self.top_bar.color_tags.setDisabled(b)

    def tree_wid_view_folder_cmd(self, root: str):
        Config.json_data["root"] = root
        self.grid_standart_load()

    def top_bar_next_back_cmd(self, root: str):
        Config.json_data["root"] = root
        self.grid_standart_load()

    def tree_wid_add_fav_cmd(self, root: str):
        name = os.path.basename(root)
        self.folders_fav_wid.add_item(name, root)
        favs: dict = Config.json_data.get("favs")
        favs[root] = name

    def tree_wid_del_fav_cmd(self, root: str):
        self.folders_fav_wid.del_item(root)

    def top_bar_open_path_btn_cmd(self, path: str):
        if not os.path.exists(path):
            return

        filepath = ""
        if os.path.isfile(path):
            if path.endswith(Config.img_ext):
                filepath = path
            path, _ = os.path.split(path)

        Config.json_data["root"] = path
        self.grid_standart_load()
        QTimer.singleShot(1500, lambda: self.grid.move_to_wid(filepath))

    def grid_search_load(self, search_text: str):
        self.top_bar_setDisabled(True)

        if self.grid:
            self.grid.disconnect()
            self.grid.close()

        self.setFocus()
        self.setWindowTitle(f"🟠\tИдет поиск: \"{search_text}\"")
        self.migaet_timer.start(400)
        ww = self.get_grid_width()
        self.grid = GridSearch(width=ww, search_text=search_text)
        self.grid.verticalScrollBar().valueChanged.connect(self.scroll_up_scroll_value)
        self.grid.search_finished.connect(lambda: self.grid_search_finished(search_text))
        self.grid.show_thumbnail_in_folder.connect(self.grid_search_move_to_wid)
        self.r_lay.addWidget(self.grid)

    def grid_search_migaet_title(self):
        if "🟠" in self.windowTitle():
            t = self.windowTitle().replace("🟠", "⚪")
        else:
            t = self.windowTitle().replace("⚪", "🟠")
        self.setWindowTitle(t)

    def grid_search_finished(self, search_text: str):
        self.migaet_timer.stop()
        self.setWindowTitle(f"🟢\tРезультаты поиска: \"{search_text}\"")
        self.grid.sort_grid(self.get_grid_width())
        self.top_bar_setDisabled(False)

    def grid_search_move_to_wid(self, src: str):
        root = os.path.dirname(src)
        Config.json_data["root"] = root
        self.grid_standart_load()
        QTimer.singleShot(1500, lambda: self.grid.move_to_wid(src))

    def grid_standart_load(self):
        if isinstance(self.grid, (GridSearch, GridStandart)):
            self.grid.close()

        self.setDisabled(True)
        self.setFocus()
        self.setWindowTitle(os.path.basename(Config.json_data.get("root")))

        self.top_bar_setDisabled(False)
        self.top_bar.search_wid.clear_search_sig.emit()
        self.top_bar.update_history()

        self.folders_tree_wid.expand_path(Config.json_data.get("root"))
    
        self.grid = GridStandart(width=self.get_grid_width())
        self.grid.finder_items_loaded.connect(lambda: self.setDisabled(False))
        self.grid.verticalScrollBar().valueChanged.connect(self.scroll_up_scroll_value)

        self.grid.add_fav_sig.connect(self.tree_wid_add_fav_cmd)
        self.grid.del_fav_sig.connect(self.tree_wid_del_fav_cmd)

        self.grid.open_folder_sig.connect(self.tree_wid_view_folder_cmd)

        self.r_lay.addWidget(self.grid)

    def scroll_up_scroll_value(self, value: int):
        if value == 0:
            self.scroll_up.hide()
        else:
            self.scroll_up.show()

    def get_grid_width(self):
        return Config.json_data.get("ww") - self.tabs_wid.width() - 180

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        Config.json_data["ww"] = self.geometry().width()
        Config.json_data["hh"] = self.geometry().height()
        self.scroll_up.move(self.width() - 70, self.height() - 70)
        self.resize_timer.stop()
        self.resize_timer.start(500)
        # return super().resizeEvent(a0)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self.hide()
        self.grid.stop_and_wait_threads()
        a0.ignore()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_F:
            if a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.top_bar.search_wid.input_wid.setFocus()

        elif a0.key() == Qt.Key.Key_W:
            if a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.hide()

        elif a0.key() == Qt.Key.Key_Q:
            if a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
                QApplication.instance().quit()

        elif a0.key() == Qt.Key.Key_Escape:
            self.setFocus()

        elif a0.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.grid.setFocus()


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
