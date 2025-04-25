import os

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QKeyEvent, QMouseEvent, QResizeEvent
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
                             QSplitter, QTabWidget, QVBoxLayout, QWidget)

from cfg import Dynamic, JsonData, Static
from utils import Utils

from ._base_items import BaseItem, SearchItem, USep, WinBase, SortItem
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
    left_menu_width = 240

    def __init__(self, dir: str = None):
        super().__init__()
        self.setMinimumSize(MainWin.min_width_, MainWin.min_height_)
        self.resize(MainWin.width_, MainWin.height_)
        if dir:
            self.main_dir = dir
        else:
            self.main_dir = os.path.expanduser("~/Downloads")
            self.main_dir = Utils.add_system_volume(self.main_dir)
        self.main_win_list: list[MainWin] = []
        # индекс 0 просмотр сеткой, индекс 1 просмотр списком
        self.view_index = 0
        self.search_item = SearchItem()
        self.resize_timer = QTimer(parent=self)
        self.resize_timer.setSingleShot(True)
        self.sort_item = SortItem()
        
        main_lay = QHBoxLayout()
        main_lay.setContentsMargins(5, 0, 5, 0)
        main_lay.setSpacing(0)
        self.setLayout(main_lay)

        self.splitter = QSplitter()
        self.splitter.setHandleWidth(12)
        main_lay.addWidget(self.splitter)

        left_wid = QWidget()
        self.splitter.addWidget(left_wid)
        left_v_lay = QVBoxLayout()
        left_v_lay.setContentsMargins(0, 0, 0, 5)
        left_v_lay.setSpacing(0)
        left_wid.setLayout(left_v_lay)

        self.menu_tabs = TabsWidget()
        left_v_lay.addWidget(self.menu_tabs)

        self.menu_tree = TreeMenu()
        self.menu_tabs.addTab(self.menu_tree, "Папки")

        self.menu_favs = FavsMenu()
        self.menu_tabs.addTab(self.menu_favs, "Избранное")

        self.tags_btn = TagsBtn()
        left_v_lay.addWidget(self.tags_btn)

        self.menu_tags = TagsMenu()
        left_v_lay.addWidget(self.menu_tags)

        self.tags_btn.click_cmd()

        right_wid = QWidget()
        self.splitter.addWidget(right_wid)

        self.r_lay = QVBoxLayout()
        self.r_lay.setContentsMargins(0, 0, 0, 0)
        self.r_lay.setSpacing(0)
        right_wid.setLayout(self.r_lay)
        
        self.bar_top = TopBar(self.search_item)
        sep_one = USep()
        self.search_bar = SearchBar(self.search_item)
        self.search_bar_sep = USep()
        self.grid = Grid(self.main_dir, self.view_index, None)
        sep_two = USep()
        self.path_bar = PathBar()
        sep = USep()
        self.sort_bar = SortBar(self.sort_item)

        self.scroll_up = ScrollUpBtn(self)
        self.scroll_up.hide()
        self.scroll_up.clicked.connect(lambda: self.grid.verticalScrollBar().setValue(0))

        self.r_lay.insertWidget(0, self.bar_top)
        self.r_lay.insertWidget(1, sep_one)
        self.r_lay.insertWidget(2, self.search_bar)
        self.r_lay.insertWidget(3, self.search_bar_sep)
        self.r_lay.insertWidget(MainWin.grid_insert_num, self.grid)
        self.r_lay.insertWidget(5, sep_two)
        self.r_lay.insertWidget(6, self.path_bar)
        self.r_lay.insertWidget(7, sep)
        self.r_lay.insertWidget(8, self.sort_bar)

        self.bar_top.new_history_item_cmd(self.main_dir)
        self.path_bar.set_new_path(self.main_dir)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes(
            [MainWin.left_menu_width, self.width() - MainWin.left_menu_width]
        )
        self.menu_tabs.setCurrentIndex(1)
        self.setup_signals()
        self.tags_btn_cmd()
        self.load_standart_grid((self.main_dir, None))

    def setup_signals(self):
        self.resize_timer.timeout.connect(self.resize_timer_cmd)
        self.splitter.splitterMoved.connect(lambda: self.resize_timer.start(MainWin.resize_ms))

        self.menu_tree.load_st_grid_sig.connect(lambda data: self.load_standart_grid(data))
        self.menu_tree.fav_cmd_sig.connect(lambda data: self.menu_favs.fav_cmd(data))
        self.menu_tree.new_history_item.connect(lambda dir: self.bar_top.new_history_item_cmd(dir))
        self.menu_tree.open_in_new_window.connect(lambda dir: self.open_in_new_window_cmd(dir))

        self.menu_favs.load_st_grid_sig.connect(lambda data: self.load_standart_grid(data))
        self.menu_favs.new_history_item.connect(lambda dir: self.bar_top.new_history_item_cmd(dir))
        self.menu_favs.open_in_new_win.connect(lambda dir: self.open_in_new_window_cmd(dir))

        self.tags_btn.clicked_.connect(lambda: self.tags_btn_cmd())

        self.menu_tags.filter_grid_sig.connect(lambda: self.grid.filter_())
        self.menu_tags.rearrange_grid_sig.connect(lambda: self.grid.rearrange())

        # перейти на директорию выше
        self.bar_top.level_up.connect(lambda: self.level_up_cmd())
        # изменить отображение сетка/список
        self.bar_top.change_view.connect(lambda index: self.change_view_cmd(index))
        # начать поиск
        self.bar_top.load_search_grid_sig.connect(lambda: self.load_search_grid())
        # очистить поиск, загрузить стандартную сетку с текущей директорией
        self.bar_top.load_st_grid_sig.connect(lambda: self.load_standart_grid((self.main_dir, None)))
        # перейти вперед/назад по истории посещений
        self.bar_top.navigate.connect(lambda dir: self.load_standart_grid((dir, None)))
        # было открыто окно настроек и был клик "очистить данные в этой папке"
        self.bar_top.clear_data_clicked.connect(lambda: self.remove_db_cmd())
        self.bar_top.open_in_new_win.connect(lambda dir: self.open_in_new_window_cmd(dir))

        self.search_bar.load_search_grid.connect(lambda: self.load_search_grid())

        self.path_bar.new_history_item.connect(lambda dir: self.bar_top.new_history_item_cmd(dir))
        self.path_bar.load_st_grid_sig.connect(lambda data: self.load_standart_grid(data))
        self.path_bar.open_img_view.connect(lambda path: self.open_img_view_cmd(path))
        self.path_bar.open_in_new_window.connect(lambda dir: self.open_in_new_window_cmd(dir))

        self.sort_bar.resize_grid_sig.connect(lambda: self.grid.resize_())
        self.sort_bar.rearrange_grid_sig.connect(lambda: self.grid.rearrange())
        self.sort_bar.sort_grid_sig.connect(lambda: self.grid.sort_())
        self.sort_bar.load_st_grid_sig.connect(lambda data: self.load_standart_grid(data))

    def open_img_view_cmd(self, path: str):
        base_item = BaseItem(path)
        base_item.setup_attrs()
        self.grid.view_thumb_cmd(base_item)

    def remove_db_cmd(self):
        """
        Удаляет базу данных в текущей директории
        """
        db = os.path.join(self.main_dir, Static.DB_FILENAME)
        if os.path.exists(db):
            os.remove(db)
            self.load_standart_grid((self.main_dir, None))

    def level_up_cmd(self):
        new_main_dir = os.path.dirname(self.main_dir)
        if new_main_dir != os.sep:
            self.load_standart_grid((new_main_dir, self.main_dir))
            self.bar_top.new_history_item_cmd(new_main_dir)
            self.main_dir = new_main_dir

    def change_view_cmd(self, index: int):
        self.view_index = index
        self.load_standart_grid((self.main_dir, None))

    def resize_timer_cmd(self):
        self.grid.resize_()
        self.grid.rearrange()

    def tags_btn_cmd(self):
        if self.menu_tags.isHidden():
            self.menu_tags.show()
        else:
            self.menu_tags.hide()

    def open_path_cmd(self, filepath: str):
        if not os.path.exists(filepath):
            return

        if filepath.endswith(Static.ext_all):
            self.main_dir = os.path.dirname(filepath)
            self.load_standart_grid((self.main_dir, filepath))
        else:
            self.main_dir = filepath
            self.load_standart_grid((self.main_dir, None))

    def open_in_new_window_cmd(self, dir: str):
        new_win = MainWin(dir)
        self.main_win_list.append(new_win)
        x, y = self.window().x(), self.window().y()
        new_win.move(x + 20, y + 20)
        new_win.show()

    def setup_grid_signals(self):
        self.grid.sort_bar_update.connect(lambda value: self.sort_bar.setup(value))
        self.grid.path_bar_update.connect(lambda dir: self.path_bar.setup(dir))
        self.grid.fav_cmd_sig.connect(lambda data: self.menu_favs.fav_cmd(data))
        self.grid.move_slider_sig.connect(lambda value: self.sort_bar.slider.move_from_keyboard(value))
        self.grid.load_st_grid_sig.connect(lambda data: self.load_standart_grid(data))
        self.grid.open_in_new_window.connect(lambda dir: self.open_in_new_window_cmd(dir))
        self.grid.level_up.connect(lambda: self.level_up_cmd())
        self.grid.new_history_item.connect(lambda dir: self.bar_top.new_history_item_cmd(dir))
        self.grid.change_view_sig.connect(lambda index: self.change_view_cmd(index))
        self.grid.force_load_images_sig.connect(lambda urls: self.grid.force_load_images_cmd(urls))
        self.grid.verticalScrollBar().valueChanged.connect(lambda value: self.scroll_up_show_hide(value))

    def load_search_grid(self):
        self.grid.deleteLater()
        self.menu_tags.reset()
        self.search_bar.show()
        self.search_bar_sep.show()
        self.bar_top.set_main_dir(self.main_dir)
        self.menu_favs.set_main_dir(self.main_dir)
        self.search_bar.show_spinner()

        self.grid = GridSearch(self.main_dir, self.view_index, None)
        self.grid.set_sort_item(self.sort_item)
        self.grid.finished_.connect(lambda id_=id(self.grid): self.finished_search_grid(id_))
        self.grid.set_search_item(self.search_item)
        self.grid.start_search()
        self.r_lay.insertWidget(MainWin.grid_insert_num, self.grid)
        self.setup_grid_signals()

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

    def load_standart_grid(self, data: tuple):
        """
        data:
        - могут быть None
        - main_dir: основная директория, которая будет отображена в виде сетки виджетов
        - url_for_select: виджет сетки, соответствующий url_for select, будет выделен
        после инициации сетки виджетов
        """
        self.grid.deleteLater()
        new_main_dir, url_for_select = data

        if new_main_dir:
            self.main_dir = new_main_dir

        if not os.path.exists(self.main_dir):
            fixed_path = Utils.fix_path_prefix(self.main_dir)
            if fixed_path:
                self.main_dir = fixed_path

        # Заголовок окна
        # Имя папки или имя избранного или имя папки (имя избранного)
        base_name = os.path.basename(self.main_dir)
        if self.main_dir in JsonData.favs:
            fav = JsonData.favs.get(self.main_dir)
            if fav != base_name:
                title = f"{base_name} ({JsonData.favs[self.main_dir]})"
            else:
                title = base_name
        else:
            title = base_name

        LoadImage.cached_images.clear()
        self.setWindowTitle(title)
        self.menu_favs.fav_cmd(("select", self.main_dir))
        self.bar_top.search_wid.clear_search()
        self.search_bar.hide()
        self.search_bar_sep.hide()
        self.bar_top.set_main_dir(self.main_dir)
        self.menu_favs.set_main_dir(self.main_dir)
        self.menu_tree.expand_path(self.main_dir)

        if self.view_index == 0:
            self.grid = GridStandart(self.main_dir, self.view_index, url_for_select)
            self.grid.set_sort_item(self.sort_item)
            self.grid.load_finder_items()

        elif self.view_index == 1:
            self.grid = GridList(self.main_dir, self.view_index)

        self.setup_grid_signals()
        self.r_lay.insertWidget(MainWin.grid_insert_num, self.grid)

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
        # wins = [
        #     i
        #     for i in QApplication.topLevelWidgets()
        #     if isinstance(i, MainWin)
        # ]

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
                self.bar_top.search_wid.setFocus()
                self.bar_top.search_wid.selectAll()

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
