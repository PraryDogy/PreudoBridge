import os

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QCloseEvent, QKeyEvent, QMouseEvent, QResizeEvent
from PyQt5.QtWidgets import (QApplication, QGridLayout, QHBoxLayout, QLabel,
                             QTabWidget, QVBoxLayout, QWidget)

from cfg import Dynamic, JsonData, Static
from signals import SignalsApp
from widgets._grid import Grid, Thumb
from widgets.bar_bottom import BarBottom
from widgets.bar_top import BarTop
from widgets.grid_search import GridSearch
from widgets.grid_standart import GridStandart
from widgets.list_file_system import ListFileSystem
from widgets.tree_favorites import TreeFavorites
from widgets.tree_folders import TreeFolders
from widgets.win_img_view import LoadImage
from widgets.tree_tags import TreeTags

class BarTabs(QTabWidget):
    def __init__(self):
        super().__init__()
        self.tabBarClicked.connect(self.tab_cmd)

    def load_last_tab(self):
        self.setCurrentIndex(Dynamic.left_menu_tab)

    def tab_cmd(self, index: int):
        self.setCurrentIndex(Dynamic.left_menu_tab)
        Dynamic.left_menu_tab = index

    def mouseClickEvent(self, a0: QMouseEvent | None) -> None:
        if a0.button() == Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(a0)
        else:
            a0.ignore()


class MainWin(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumWidth(200)

        ww, hh = Dynamic.ww, Dynamic.hh
        self.resize(ww, hh)
        self.setMinimumSize(800, 500)
        
        resize_cmd_ = lambda: self.grid.rearrange(self.get_grid_width())
        self.resize_timer = QTimer(parent=self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(resize_cmd_)

        self.migaet_timer = QTimer(parent=self)
        self.migaet_timer.timeout.connect(self.blink_title)

        main_lay = QHBoxLayout()
        main_lay.setContentsMargins(5, 0, 5, 0)
        main_lay.setSpacing(0)
        self.setLayout(main_lay)

        left_wid = QWidget()
        left_wid.setFixedWidth(Static.LEFT_MENU_W)
        main_lay.addWidget(left_wid)
        left_v_lay = QVBoxLayout()
        left_v_lay.setContentsMargins(0, 0, 0, 5)
        left_v_lay.setSpacing(5)
        left_wid.setLayout(left_v_lay)

        self.bar_tabs = BarTabs()
        self.bar_tabs.setFixedWidth(Static.LEFT_MENU_W)
        left_v_lay.addWidget(self.bar_tabs)

        self.tree_folders = TreeFolders()
        self.bar_tabs.addTab(self.tree_folders, "Папки")

        self.tree_favorites = TreeFavorites()
        self.bar_tabs.addTab(self.tree_favorites, "Избранное")

        tree_tags = TreeTags()
        left_v_lay.addWidget(tree_tags)

        self.bar_tabs.load_last_tab()

        right_wid = QWidget()
        main_lay.addWidget(right_wid)

        self.r_lay = QVBoxLayout()
        self.r_lay.setContentsMargins(5, 0, 0, 0)
        self.r_lay.setSpacing(0)
        right_wid.setLayout(self.r_lay)
        
        self.bar_top = BarTop()
        self.r_lay.addWidget(self.bar_top, alignment=Qt.AlignmentFlag.AlignTop)
        
        self.bar_bottom = BarBottom()
        self.r_lay.insertWidget(2, self.bar_bottom, alignment=Qt.AlignmentFlag.AlignBottom)

        self.scroll_up = QLabel(parent=self, text=Static.UP_ARROW_SYM)
        self.scroll_up.hide()
        self.scroll_up.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_up.mouseReleaseEvent = lambda e: self.grid.verticalScrollBar().setValue(0)
        self.scroll_up.setFixedSize(40, 40)
        self.scroll_up.setStyleSheet(
            f"""
            background-color: {Static.GRAY_UP_BTN};
            border-radius: 20px;
            """
            )

        # они должны быть именно тут
        self.grid: Grid = Grid(self.get_grid_width())

        SignalsApp.instance.load_standart_grid.connect(self.load_standart_grid)
        SignalsApp.instance.load_search_grid.connect(self.load_search_grid)
        SignalsApp.instance.set_search_title.connect(self.search_finished)
        SignalsApp.instance.open_path.connect(self.open_path_cmd)

        SignalsApp.instance.load_standart_grid_cmd(
            path=JsonData.root,
            prev_path=None
        )

    def open_path_cmd(self, filepath: str):
        if not os.path.exists(filepath):
            return

        if filepath.endswith(Static.IMG_EXT):
            JsonData.root = os.path.dirname(filepath)
            
            SignalsApp.instance.load_standart_grid_cmd(
                path=JsonData.root,
                prev_path=None
            )

            self.move_to_wid_delayed(filepath)
        else:
            JsonData.root = filepath

            SignalsApp.instance.load_standart_grid_cmd(
                path=JsonData.root,
                prev_path=None
            )

    def load_search_grid(self, search_text: str):
        self.grid.close()
        self.bar_top.filters_btn.reset_filters()

        t = [
            f"🟠\tИдет поиск в \"{os.path.basename(JsonData.root)}\""
        ]
        self.setWindowTitle("".join(t))

        self.migaet_timer.start(400)
        ww = self.get_grid_width()
        self.grid = GridSearch(width=ww, search_text=search_text)
        self.grid.verticalScrollBar().valueChanged.connect(self.scroll_up_scroll_value)
        self.r_lay.insertWidget(1, self.grid)
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

    def load_standart_grid(self, data: dict):

        JsonData.root = data.get("path")
        LoadImage.cache.clear()
        self.grid.close()
        self.setWindowTitle(os.path.basename(JsonData.root))
        SignalsApp.instance.fav_cmd.emit({"cmd": "select", "src": JsonData.root})
        self.bar_top.search_wid.clear_search.emit()
        self.bar_top.filters_btn.reset_filters()

        if Dynamic.grid_view_type == 1:
            self.grid = ListFileSystem()

        elif Dynamic.grid_view_type == 0:

            self.grid = GridStandart(
                width=self.get_grid_width(),
                prev_path=data.get("prev_path")
            )

        self.grid.verticalScrollBar().valueChanged.connect(
            self.scroll_up_scroll_value
        )

        self.tree_folders.expand_path(JsonData.root)

        self.r_lay.insertWidget(1, self.grid)
        self.grid.setFocus()

        prev_path = data.get("prev_path")
        wid = Thumb.path_to_wid.get(prev_path)

    def scroll_up_scroll_value(self, value: int):
        if value == 0:
            self.scroll_up.hide()
        else:
            self.scroll_up.show()

    def get_grid_width(self):
        return Dynamic.ww - self.bar_tabs.width() - 180
    
    def user_exit(self):

        # предотвращает segmentation fault

        wids = (
            self.scroll_up,
            self.tree_favorites,
            self.tree_folders,
            self.bar_tabs,
            self.bar_top,
            self.grid,
            self.bar_bottom
            )
        
        for i in wids:
            i.close()

        for i in self.findChildren(QWidget):
            i.close()

        a = QApplication.instance().children()
        for i in a:
            del(i)
        

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        Dynamic.ww = self.geometry().width()
        Dynamic.hh = self.geometry().height()
        self.scroll_up.move(self.width() - 70, self.height() - 110)
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
                self.bar_top.search_wid.search_wid.setFocus()
                self.bar_top.search_wid.search_wid.selectAll()

            elif a0.key() == Qt.Key.Key_W:
                self.hide()

            elif a0.key() == Qt.Key.Key_Q:
                QApplication.instance().quit()
        
            elif a0.key() == Qt.Key.Key_1:
                self.bar_top.view_type_btn.set_view_type_cmd(0)
            
            elif a0.key() == Qt.Key.Key_2:
                self.bar_top.view_type_btn.set_view_type_cmd(1)

        elif a0.key() == Qt.Key.Key_Escape:
            self.setFocus()

        return super().keyPressEvent(a0)
