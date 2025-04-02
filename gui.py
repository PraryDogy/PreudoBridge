import os

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QKeyEvent, QMouseEvent, QResizeEvent
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QApplication, QHBoxLayout, QLabel,
                             QTabWidget, QVBoxLayout, QWidget)

from cfg import Dynamic, JsonData, Static
from signals import SignalsApp
from widgets._grid import Grid
from widgets.bar_bottom import BarBottom
from widgets.bar_top import BarTop
from widgets.grid_search import GridSearch
from widgets.grid_standart import GridStandart
from widgets.list_file_system import ListFileSystem
from widgets.tree_favorites import TreeFavorites
from widgets.tree_folders import TreeFolders
from widgets.tree_tags import TreeTags
from widgets.win_img_view import LoadImage

ARROW_UP = "\u25B2" # ▲


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


class ShowHideTags(QWidget):
    clicked_ = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.setFixedHeight(22)

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(0, 0, 0, 0)
        self.setLayout(v_lay)

        self.svg = QSvgWidget()
        self.svg.setFixedSize(20, 20)
        self.svg.load(Static.HIDE_SVG)
        v_lay.addWidget(self.svg, alignment=Qt.AlignmentFlag.AlignCenter)

        self.hide_svg = True

    def click_cmd(self):
        if self.hide_svg:
            self.svg.load(Static.SHOW_SVG)
            self.hide_svg = False

        else:
            self.svg.load(Static.HIDE_SVG)
            self.hide_svg = True

        self.clicked_.emit()

    def mouseReleaseEvent(self, a0):
        if a0.button() == Qt.MouseButton.LeftButton:
            self.click_cmd()


class MainWin(QWidget):
    def __init__(self):

        if not self.__class__.__name__ == Static.MAIN_WIN_NAME:

            text = (
                f"gui.py > имя класса {self.__class__.__name__}",
                f"должно соответствовать cfg.py > MAIN_WIN_NAME ({Static.MAIN_WIN_NAME})"
            )

            raise Exception ("\n".join(text))

        super().__init__()
        self.setMinimumWidth(200)

        ww, hh = Dynamic.ww, Dynamic.hh
        self.resize(ww, hh)
        self.setMinimumSize(800, 500)
        
        # resize_cmd_ = lambda: self.grid.rearrange(self.get_grid_width())
        resize_cmd_ = lambda: self.grid.resize_(width=self.get_grid_width())
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
        left_v_lay.setSpacing(0)
        left_wid.setLayout(left_v_lay)

        self.bar_tabs = BarTabs()
        self.bar_tabs.setFixedWidth(Static.LEFT_MENU_W)
        left_v_lay.addWidget(self.bar_tabs)

        self.tree_folders = TreeFolders()
        self.bar_tabs.addTab(self.tree_folders, "Папки")

        self.tree_favorites = TreeFavorites()
        self.bar_tabs.addTab(self.tree_favorites, "Избранное")

        show_hide_tags_btn = ShowHideTags()
        show_hide_tags_btn.clicked_.connect(self.show_hide_tags)
        left_v_lay.addWidget(show_hide_tags_btn)

        self.tree_tags = TreeTags()
        left_v_lay.addWidget(self.tree_tags, alignment=Qt.AlignmentFlag.AlignCenter)

        show_hide_tags_btn.click_cmd()

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

        self.scroll_up = QLabel(parent=self, text=ARROW_UP)
        self.scroll_up.hide()
        self.scroll_up.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_up.mouseReleaseEvent = lambda e: self.grid.verticalScrollBar().setValue(0)
        self.scroll_up.setFixedSize(40, 40)
        self.scroll_up.setStyleSheet(
            f"""
            background-color: {Static.GRAY_GLOBAL};
            border-radius: 20px;
            """
            )

        # они должны быть именно тут
        self.grid: Grid = Grid(self.get_grid_width())

        SignalsApp.instance.load_standart_grid.connect(self.load_standart_grid)
        SignalsApp.instance.load_search_grid.connect(self.load_search_grid)
        SignalsApp.instance.set_search_title.connect(self.search_finished)
        SignalsApp.instance.open_path.connect(self.open_path_cmd)
        SignalsApp.instance.load_any_grid.connect(self.load_any_grid)

        SignalsApp.instance.load_standart_grid.emit((JsonData.root, None))

    def show_hide_tags(self):
        if self.tree_tags.isHidden():
            self.tree_tags.show()
        else:
            self.tree_tags.hide()

    def open_path_cmd(self, filepath: str):
        if not os.path.exists(filepath):
            return

        if filepath.endswith(Static.IMG_EXT):
            JsonData.root = os.path.dirname(filepath)
            SignalsApp.instance.load_standart_grid.emit((JsonData.root, filepath))
        else:
            JsonData.root = filepath
            SignalsApp.instance.load_standart_grid.emit((JsonData.root, None))

    def load_search_grid(self, search_text: str):
        self.grid.close()
        self.tree_tags.reset()

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

    def load_any_grid(self, data: tuple):
        if isinstance(self.grid, GridSearch):
            self.grid.order_()
        else:
            self.load_standart_grid(data)

    def load_standart_grid(self, data: tuple):
        path_for_grid, path_for_select = data
        JsonData.root = path_for_grid
        LoadImage.cache.clear()
        self.grid.close()

        base_name = os.path.basename(JsonData.root)
        if JsonData.root in JsonData.favs:
            fav = JsonData.favs[JsonData.root]
            if fav != base_name:
                title = f"{base_name} ({JsonData.favs[JsonData.root]})"
            else:
                title = base_name
        else:
            title = base_name

        self.setWindowTitle(title)
        SignalsApp.instance.fav_cmd.emit(("select", JsonData.root))
        self.bar_top.search_wid.clear_search.emit()

        if Dynamic.grid_view_type == 1:
            self.grid = ListFileSystem()

        elif Dynamic.grid_view_type == 0:

            self.grid = GridStandart(self.get_grid_width(), path_for_select)

        self.grid.verticalScrollBar().valueChanged.connect(
            self.scroll_up_scroll_value
        )

        self.tree_folders.expand_path(JsonData.root)

        self.r_lay.insertWidget(1, self.grid)
        self.grid.setFocus()

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
                self.bar_top.change_view_cmd(index=0)
            
            elif a0.key() == Qt.Key.Key_2:
                self.bar_top.change_view_cmd(index=1)

        elif a0.key() == Qt.Key.Key_Escape:
            self.setFocus()

        return super().keyPressEvent(a0)
