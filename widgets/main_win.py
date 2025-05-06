import os

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QKeyEvent, QMouseEvent, QResizeEvent
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
                             QSplitter, QTabWidget, QVBoxLayout, QWidget)

from cfg import JsonData, Static
from utils import Utils

from ._base_items import (BaseItem, MainWinItem, SearchItem, SortItem, USep,
                          WinBase)
from .favs_menu import FavsMenu
from .grid import Grid
from .grid_list import GridList
from .grid_search import GridSearch
from .grid_standart import GridStandart
from .img_view_win import LoadImage
from .path_bar import PathBar
from .search_bar import SearchBar
from .sort_bar import SortBar
from .tags_menu import TagsMenu
from .top_bar import TopBar
from .tree_menu import TreeMenu

ARROW_UP = "\u25B2" # ▲


class TabsWidget(QTabWidget):
    def __init__(self):
        super().__init__()
        self.tabBarClicked.connect(self.tab_cmd)

    def tab_cmd(self, index: int):
        self.setCurrentIndex(index)

    def mouseClickEvent(self, a0: QMouseEvent | None) -> None:
        if a0.button() == Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(a0)
        else:
            a0.ignore()


class TagsBtn(QWidget):
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


class ScrollUpBtn(QLabel):
    clicked = pyqtSignal()

    def __init__(self, parent: QWidget):
        super().__init__(ARROW_UP, parent)
        self.setFixedSize(40, 40)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"""
            background-color: {Static.GRAY_GLOBAL};
            border-radius: 20px;
            """
            )
        
    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        return super().mouseReleaseEvent(ev)


class MainWin(WinBase):
    resize_ms = 100
    grid_insert_num = 4
    width_ = 1050
    height_ = 700
    min_width_ = 800
    min_height_ = 500
    left_menu_w = 240

    def __init__(self, dir: str = None):
        super().__init__()
        self.main_win_list: list[MainWin] = []
        # индекс 0 просмотр сеткой, индекс 1 просмотр списком
        self.view_index: int = 0
        self.search_item: SearchItem = SearchItem()
        self.main_win_item: MainWinItem = MainWinItem()
        self.sort_item: SortItem = SortItem()

        self.setMinimumSize(MainWin.min_width_, MainWin.min_height_)
        self.resize(MainWin.width_, MainWin.height_)

        if dir:
            self.main_win_item.main_dir = dir
        else:
            dir = os.path.expanduser("~/Downloads")
            dir = Utils.add_system_volume(dir)
            self.main_win_item.main_dir = dir

        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.resize_timer_cmd)

        main_lay = QHBoxLayout()
        main_lay.setContentsMargins(5, 0, 5, 0)
        main_lay.setSpacing(0)
        self.setLayout(main_lay)

        self.splitter = QSplitter()
        self.splitter.setHandleWidth(12)
        main_lay.addWidget(self.splitter)

        left_wid = QWidget()
        left_v_lay = QVBoxLayout()
        left_v_lay.setContentsMargins(0, 0, 0, 5)
        left_v_lay.setSpacing(0)
        left_wid.setLayout(left_v_lay)
        self.tabs_widget = TabsWidget()
        left_v_lay.addWidget(self.tabs_widget)
        self.tree_menu = TreeMenu(self.main_win_item)
        self.tabs_widget.addTab(self.tree_menu, "Папки")
        self.favs_menu = FavsMenu(self.main_win_item)
        self.tabs_widget.addTab(self.favs_menu, "Избранное")
        self.tags_menu_btn = TagsBtn()
        left_v_lay.addWidget(self.tags_menu_btn)
        self.tags_menu = TagsMenu()
        left_v_lay.addWidget(self.tags_menu)

        right_wid = QWidget()
        self.r_lay = QVBoxLayout()
        self.r_lay.setContentsMargins(0, 0, 0, 0)
        self.r_lay.setSpacing(0)
        right_wid.setLayout(self.r_lay)
        self.top_bar = TopBar(self.main_win_item, self.search_item)
        sep_one = USep()
        self.search_bar = SearchBar(self.search_item)
        self.search_bar_sep = USep()
        self.grid = Grid(self.view_index, self.main_win_item)
        sep_two = USep()
        self.path_bar = PathBar(self.main_win_item)
        sep = USep()
        self.sort_bar = SortBar(self.sort_item, self.main_win_item)

        self.scroll_up = ScrollUpBtn(self)
        self.scroll_up.hide()
        self.scroll_up.clicked.connect(lambda: self.grid.verticalScrollBar().setValue(0))

        self.splitter.addWidget(left_wid)
        self.splitter.addWidget(right_wid)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([MainWin.left_menu_w, self.width() - MainWin.left_menu_w])

        self.top_bar.new_history_item_cmd(self.main_win_item.main_dir)
        self.path_bar.set_new_path(self.main_win_item.main_dir)
        self.tabs_widget.setCurrentIndex(1)
        self.tags_update_visibility()
        self.tags_menu_btn.click_cmd()

        self.r_lay.insertWidget(0, self.top_bar)
        self.r_lay.insertWidget(1, sep_one)
        self.r_lay.insertWidget(2, self.search_bar)
        self.r_lay.insertWidget(3, self.search_bar_sep)
        self.r_lay.insertWidget(MainWin.grid_insert_num, self.grid)
        self.r_lay.insertWidget(5, sep_two)
        self.r_lay.insertWidget(6, self.path_bar)
        self.r_lay.insertWidget(7, sep)
        self.r_lay.insertWidget(8, self.sort_bar)

        self.setup_signals()
        self.load_st_grid()

    def setup_signals(self):
        self.splitter.splitterMoved.connect(lambda: self.resize_timer.start(MainWin.resize_ms))

        self.tree_menu.load_st_grid_sig.connect(lambda: self.load_st_grid())
        self.tree_menu.fav_cmd_sig.connect(lambda data: self.favs_menu.fav_cmd(data))
        self.tree_menu.new_history_item.connect(lambda dir: self.top_bar.new_history_item_cmd(dir))
        self.tree_menu.open_in_new_window.connect(lambda dir: self.open_in_new_window_cmd(dir))

        self.favs_menu.load_st_grid_sig.connect(lambda: self.load_st_grid())
        self.favs_menu.new_history_item.connect(lambda dir: self.top_bar.new_history_item_cmd(dir))
        self.favs_menu.open_in_new_win.connect(lambda dir: self.open_in_new_window_cmd(dir))

        self.tags_menu_btn.clicked_.connect(lambda: self.tags_update_visibility())

        self.tags_menu.filter_grid_sig.connect(lambda: self.grid.filter_())
        self.tags_menu.rearrange_grid_sig.connect(lambda: self.grid.rearrange())

        self.top_bar.level_up.connect(lambda: self.level_up_cmd())
        self.top_bar.change_view.connect(lambda index: self.change_view_cmd(index))
        self.top_bar.load_search_grid_sig.connect(lambda: self.load_search_grid())
        self.top_bar.load_st_grid_sig.connect(lambda: self.load_st_grid())
        self.top_bar.navigate.connect(lambda: self.load_st_grid())
        self.top_bar.clear_data_clicked.connect(lambda: self.remove_db_cmd())
        self.top_bar.open_in_new_win.connect(lambda dir: self.open_in_new_window_cmd(dir))

        self.search_bar.load_search_grid.connect(lambda: self.load_search_grid())

        self.path_bar.new_history_item.connect(lambda dir: self.top_bar.new_history_item_cmd(dir))
        self.path_bar.load_st_grid_sig.connect(lambda: self.load_st_grid())
        self.path_bar.open_img_view.connect(lambda path: self.open_img_view_cmd(path))
        self.path_bar.open_in_new_window.connect(lambda dir: self.open_in_new_window_cmd(dir))

        self.sort_bar.resize_grid_sig.connect(lambda: self.grid.resize_())
        self.sort_bar.rearrange_grid_sig.connect(lambda: self.grid.rearrange())
        self.sort_bar.sort_grid_sig.connect(lambda: self.grid.sort_())
        self.sort_bar.load_st_grid_sig.connect(lambda: self.load_st_grid())

    def open_img_view_cmd(self, path: str):
        base_item = BaseItem(path)
        base_item.setup_attrs()
        self.grid.view_thumb_cmd(base_item)

    def remove_db_cmd(self):
        """
        Удаляет базу данных в текущей директории
        """
        db = os.path.join(self.main_win_item.main_dir, Static.DB_FILENAME)
        if os.path.exists(db):
            os.remove(db)
            self.load_st_grid()

    def level_up_cmd(self):
        new_main_dir = os.path.dirname(self.main_win_item.main_dir)
        if new_main_dir != os.sep:
            self.main_win_item.immortal_urls = [self.main_win_item.main_dir]
            self.main_win_item.main_dir = new_main_dir
            self.load_st_grid()
            self.top_bar.new_history_item_cmd(new_main_dir)

    def change_view_cmd(self, index: int):
        if index == self.view_index:
            return
        self.view_index = index
        self.load_st_grid()

    def resize_timer_cmd(self):
        self.grid.resize_()
        self.grid.rearrange()

    def tags_update_visibility(self):
        if self.tags_menu.isHidden():
            self.tags_menu.show()
        else:
            self.tags_menu.hide()

    def open_path_cmd(self, filepath: str):
        if not os.path.exists(filepath):
            return

        if filepath.endswith(Static.ext_all):
            self.main_win_item.main_dir = os.path.dirname(filepath)
            self.main_win_item.urls = [filepath]
            self.load_st_grid()
        else:
            self.main_win_item.main_dir = filepath
            self.load_st_grid()

    def open_in_new_window_cmd(self, dir: str):
        new_win = MainWin(dir)
        self.main_win_list.append(new_win)
        x, y = self.window().x(), self.window().y()
        new_win.move(x + 20, y + 20)
        new_win.show()

    def setup_grid_signals(self):
        self.grid.sort_bar_update.connect(lambda value: self.sort_bar.setup(value))
        self.grid.path_bar_update.connect(lambda dir: self.path_bar.setup(dir))
        self.grid.fav_cmd_sig.connect(lambda data: self.favs_menu.fav_cmd(data))
        self.grid.move_slider_sig.connect(lambda value: self.sort_bar.slider.move_from_keyboard(value))
        self.grid.load_st_grid_sig.connect(lambda: self.load_st_grid())
        self.grid.open_in_new_window.connect(lambda dir: self.open_in_new_window_cmd(dir))
        self.grid.level_up.connect(lambda: self.level_up_cmd())
        self.grid.new_history_item.connect(lambda dir: self.top_bar.new_history_item_cmd(dir))
        self.grid.change_view_sig.connect(lambda index: self.change_view_cmd(index))
        self.grid.force_load_images_sig.connect(lambda urls: self.grid.force_load_images_cmd(urls))
        self.grid.verticalScrollBar().valueChanged.connect(lambda value: self.scroll_up_show_hide(value))

    def safe_delete_grid(self):
        # если напрямую удалять сетку, то мы обязательно наткнемся на 
        # bus error, segmentation fault, fatal error no python frame
        # поэтому мы сначала скрываем старую сетку
        # затем по таймеру удаляем ее
        old_grid = self.grid
        old_grid.hide()
        old_grid.setParent(None)
        QTimer.singleShot(3000, lambda: old_grid.deleteLater())

    def load_search_grid(self):
        self.search_bar.show()
        self.search_bar.show_spinner()
        self.search_bar_sep.show()
        self.tags_menu.reset()

        self.safe_delete_grid()
        self.grid = GridSearch(self.main_win_item, self.view_index)
        self.grid.setParent(self)
        self.grid.set_sort_item(self.sort_item)
        self.grid.finished_.connect(lambda id_=id(self.grid): self.finished_search_grid(id_))
        self.grid.set_search_item(self.search_item)
        self.grid.start_search()
        self.r_lay.insertWidget(MainWin.grid_insert_num, self.grid)
        self.setup_grid_signals()
        self.grid.setFocus()

    def finished_search_grid(self, id_: int):
        """
        Обрабатывает сигнал завершения поиска в GridSearch.

        - При подключении сигнала к слоту передаётся идентификатор (id) текущей активной сетки.
        - В момент получения сигнала проверяется, совпадает ли id_ с id текущей self.grid.
        - Если совпадает — скрывает индикатор загрузки (spinner) в панели поиска.
        - Если не совпадает — сигнал пришёл от устаревшей сетки, игнорируем.

        Это предотвращает реакцию на завершение поиска от уже неактуальных экземпляров GridSearch,
        которые могли быть заменены во время ожидания завершения предыдущего поиска.
        """
        if id_ == id(self.grid):
            self.search_bar.hide_spinner()

    def load_st_grid(self):
        """
        - dir: основная директория, которая будет отображена в виде сетки виджетов
        """
        # при удалении сетки срабатывает кастомный метод deleteLater
        # который обновляет main_win_item.urls, и если нет выделенных
        # виджетов, то будет будет пустым
        # обходим это, сохранив url при level_up_cmd в main_win_item.level_up_url
        # чтобы при level_up_cmd выделась предыдущая папка
        if self.main_win_item.immortal_urls:
            self.main_win_item.urls = self.main_win_item.immortal_urls.copy()
            self.main_win_item.immortal_urls.clear()

        if not os.path.exists(self.main_win_item.main_dir):
            fixed_path = Utils.fix_path_prefix(self.main_win_item.main_dir)
            if fixed_path:
                self.main_win_item.main_dir = fixed_path

        LoadImage.cached_images.clear()
        self.setWindowTitle(os.path.basename(self.main_win_item.main_dir))
        self.favs_menu.fav_cmd(("select", self.main_win_item.main_dir))
        self.top_bar.search_wid.clear_search()
        self.search_bar.hide()
        self.search_bar_sep.hide()
        self.tree_menu.expand_path(self.main_win_item.main_dir)

        self.safe_delete_grid()

        if self.view_index == 0:
            self.grid = GridStandart(self.main_win_item, self.view_index)
            self.grid.setParent(self)
            self.grid.set_sort_item(self.sort_item)
            self.grid.load_finder_items()
            self.sort_bar.sort_frame.setDisabled(False)
            self.sort_bar.slider.setDisabled(False)

        elif self.view_index == 1:
            self.grid = GridList(self.main_win_item, self.view_index)
            self.grid.setParent(self)
            self.grid.set_first_col_width()
            self.sort_bar.sort_frame.setDisabled(True)
            self.sort_bar.slider.setDisabled(True)

        self.setup_grid_signals()
        self.r_lay.insertWidget(MainWin.grid_insert_num, self.grid)
        QTimer.singleShot(400, self.grid.setFocus)

    def scroll_up_show_hide(self, value: int):
        if value == 0:
            self.scroll_up.hide()
        else:
            self.scroll_up.show()
    
    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        MainWin.width_ = self.geometry().width()
        MainWin.height_ = self.geometry().height()
        self.scroll_up.move(self.width() - 70, self.height() - 110)
        self.resize_timer.stop()
        self.resize_timer.start(MainWin.resize_ms)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        if len(WinBase.wins) > 1:
            self.deleteLater()
        else:
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
                self.top_bar.search_wid.setFocus()
                self.top_bar.search_wid.selectAll()

            elif a0.key() == Qt.Key.Key_W:
                self.close()

            elif a0.key() == Qt.Key.Key_Q:
                QApplication.instance().quit()
        
            elif a0.key() == Qt.Key.Key_1:
                self.change_view_cmd(0)
            
            elif a0.key() == Qt.Key.Key_2:
                self.change_view_cmd(1)

        elif a0.key() == Qt.Key.Key_Escape:
            self.setFocus()

        return super().keyPressEvent(a0)
