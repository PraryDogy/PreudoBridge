import os

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QCloseEvent, QKeyEvent, QMouseEvent, QResizeEvent
from PyQt5.QtWidgets import (QApplication, QGridLayout, QHBoxLayout, QLabel,
                             QTabWidget, QVBoxLayout, QWidget)

from cfg import IMG_EXT, LEFT_MENU_W, UP_ARROW_SYM, JsonData
from signals import SignalsApp
from widgets._grid import Grid
from widgets.bar_bottom import BarBottom
from widgets.bar_top import BarTop
from widgets.grid_search import GridSearch
from widgets.grid_standart import GridStandart
from widgets.list_standart import ListStandart
from widgets.tree_favorites import TreeFavorites
from widgets.tree_folders import TreeFolders


class BarTabs(QTabWidget):
    def __init__(self):
        super().__init__()
        self.tabBarClicked.connect(self.tab_cmd)

    def load_last_tab(self):
        self.setCurrentIndex(JsonData.tab_bar)

    def tab_cmd(self, index: int):
        self.setCurrentIndex(JsonData.tab_bar)
        JsonData.tab_bar = index

    def mouseClickEvent(self, a0: QMouseEvent | None) -> None:
        if a0.button() == Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(a0)
        else:
            a0.ignore()


class SimpleFileExplorer(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumWidth(200)

        ww, hh = JsonData.ww, JsonData.hh
        self.resize(ww, hh)
        self.setMinimumSize(830, 500)

        self.resize_timer = QTimer(parent=self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(lambda: self.grid.rearrange(self.get_grid_width()))

        self.migaet_timer = QTimer(parent=self)
        self.migaet_timer.timeout.connect(self.blink_title)

        main_lay = QVBoxLayout()
        main_lay.setContentsMargins(5, 5, 5, 5)
        main_lay.setSpacing(0)
        self.setLayout(main_lay)

        splitter_wid = QWidget()
        main_lay.addWidget(splitter_wid)

        splitter_lay = QHBoxLayout()
        splitter_lay.setContentsMargins(0, 0, 0, 0)
        splitter_lay.setSpacing(0)
        splitter_wid.setLayout(splitter_lay)

        self.bar_tabs = BarTabs()
        self.bar_tabs.setFixedWidth(LEFT_MENU_W)
        splitter_lay.addWidget(self.bar_tabs)

        self.folders_tree_wid = TreeFolders()
        self.bar_tabs.addTab(self.folders_tree_wid, "Папки")

        self.folders_fav_wid = TreeFavorites()
        self.bar_tabs.addTab(self.folders_fav_wid, "Избранное")

        self.bar_tabs.addTab(QLabel("Тут будут каталоги"), "Каталог")

        self.bar_tabs.load_last_tab()

        right_wid = QWidget()
        splitter_lay.addWidget(right_wid)

        self.r_lay = QGridLayout()
        self.r_lay.setContentsMargins(0, 0, 0, 0)
        self.r_lay.setSpacing(0)
        right_wid.setLayout(self.r_lay)
        
        self.bar_top = BarTop()
        self.r_lay.addWidget(self.bar_top, 0, 0, alignment=Qt.AlignmentFlag.AlignTop)
        
        self.bar_bottom = BarBottom()
        self.r_lay.addWidget(self.bar_bottom, 2, 0, alignment=Qt.AlignmentFlag.AlignBottom)

        self.scroll_up = QLabel(parent=self, text=UP_ARROW_SYM)
        self.scroll_up.hide()
        self.scroll_up.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_up.mouseReleaseEvent = lambda e: self.grid.verticalScrollBar().setValue(0)
        self.scroll_up.setFixedSize(40, 40)
        self.scroll_up.setStyleSheet(
            """
            background-color: rgba(128, 128, 128, 0.40);
            border-radius: 20px;
            """
            )

        # они должны быть именно тут
        self.grid: Grid = Grid(self.get_grid_width())
        SignalsApp.all.load_standart_grid.connect(self.load_standart_grid)
        SignalsApp.all.load_search_grid.connect(self.load_search_grid)
        SignalsApp.all.search_finished.connect(self.search_finished)
        SignalsApp.all.show_in_folder.connect(self.move_to_wid_delayed)
        SignalsApp.all.open_path.connect(self.open_path_cmd)

        from utils import Threads
        Threads.mutex.lock()

        self.load_standart_grid()

    def open_path_cmd(self, filepath: str):
        if not os.path.exists(filepath):
            return

        if filepath.endswith(IMG_EXT):
            JsonData.root = os.path.dirname(filepath)
            self.load_standart_grid()
            self.move_to_wid_delayed(filepath)
        else:
            JsonData.root = filepath
            self.load_standart_grid()

    def load_search_grid(self, search_text: str):
        self.bar_top.view_type_btn.setCurrentIndex(0)
        JsonData.list_view = False
        self.bar_top.filters_btn.reset_filters()

        self.grid_close()

        self.setWindowTitle(f"🟠\tИдет поиск: \"{search_text}\" в \"{os.path.basename(JsonData.root)}\"")
        self.migaet_timer.start(400)
        ww = self.get_grid_width()
        self.grid = GridSearch(width=ww, search_text=search_text)
        self.grid.verticalScrollBar().valueChanged.connect(self.scroll_up_scroll_value)
        self.r_lay.addWidget(self.grid, 1, 0)
        self.grid.setFocus()

    def blink_title(self):
        if "🟠" in self.windowTitle():
            t = self.windowTitle().replace("🟠", "⚪")
        else:
            t = self.windowTitle().replace("⚪", "🟠")
        self.setWindowTitle(t)

    def search_finished(self, search_text: str):
        self.migaet_timer.stop()
        self.setWindowTitle(f"🟢\tРезультаты поиска: \"{search_text}\"")
        self.grid.order_()

    def move_to_wid_delayed(self, filepath: str):
        JsonData.root = os.path.dirname(filepath)
        self.load_standart_grid()
        QTimer.singleShot(1500, lambda: self.grid.select_new_widget(filepath))

    def load_standart_grid(self, root: str = None):
        if root:
            JsonData.root = root

        self.setWindowTitle(os.path.basename(JsonData.root))
        self.grid_close()

        SignalsApp.all.fav_cmd.emit("select", JsonData.root)

        self.bar_top.search_wid.clear_search.emit()
        self.bar_top.filters_btn.reset_filters()

        if JsonData.list_view:
            self.grid = ListStandart()
            self.grid.verticalScrollBar().valueChanged.connect(self.scroll_up_scroll_value)
        else:
            self.grid = GridStandart(width=self.get_grid_width())
            self.grid.verticalScrollBar().valueChanged.connect(self.scroll_up_scroll_value)

        self.folders_tree_wid.expand_path(JsonData.root)

        self.r_lay.addWidget(self.grid, 1, 0)
        self.grid.setFocus()

    def grid_close(self):
        self.grid.disconnect()
        self.grid.close()

    def scroll_up_scroll_value(self, value: int):
        if value == 0:
            self.scroll_up.hide()
        else:
            self.scroll_up.show()

    def get_grid_width(self):
        return JsonData.ww - self.bar_tabs.width() - 180

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        JsonData.ww = self.geometry().width()
        JsonData.hh = self.geometry().height()
        self.scroll_up.move(self.width() - 70, self.height() - 100)
        self.resize_timer.stop()
        self.resize_timer.start(500)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self.hide()
        a0.ignore()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:  
        if a0.key() in (Qt.Key.Key_Right, Qt.Key.Key_Left, Qt.Key.Key_Space, Qt.Key.Key_Return):
            if not self.grid.hasFocus():
                self.grid.setFocus()
                self.grid.keyPressEvent(a0)

        if a0.modifiers() & Qt.KeyboardModifier.ControlModifier and a0.key() == Qt.Key.Key_Up:
            if not self.grid.hasFocus():
                self.grid.setFocus()
                self.grid.keyPressEvent(a0)

        elif a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if a0.key() == Qt.Key.Key_F:
                self.bar_top.search_wid.input_wid.setFocus()
                self.bar_top.search_wid.input_wid.selectAll()

            elif a0.key() == Qt.Key.Key_W:
                self.hide()

            elif a0.key() == Qt.Key.Key_Q:
                QApplication.instance().quit()
        
            elif a0.key() == Qt.Key.Key_1:
                self.bar_top.view_type_btn.set_view_cmd(0)
            
            elif a0.key() == Qt.Key.Key_2:
                self.bar_top.view_type_btn.set_view_cmd(1)

        elif a0.key() == Qt.Key.Key_Escape:
            self.setFocus()

        return super().keyPressEvent(a0)
