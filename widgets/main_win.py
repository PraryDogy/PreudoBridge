import gc
import os
import subprocess

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import (QCloseEvent, QKeyEvent, QMouseEvent, QPalette,
                         QResizeEvent)
from PyQt5.QtWidgets import (QApplication, QHBoxLayout, QLabel, QSplitter,
                             QTabWidget, QVBoxLayout, QWidget)

from cfg import JsonData, Static
from system.items import BaseItem, MainWinItem, SearchItem, SortItem
from system.paletes import UPallete
from system.shared_utils import SharedUtils
from system.tasks import (AutoCacheCleaner, PathFinderTask, RatingTask,
                          UThreadPool)
from system.utils import Utils

from ._base_widgets import USep, WinBase
from .bar_macos import BarMacos
from .cache_download_win import CacheDownloadWin
from .favs_menu import FavsMenu
from .go_win import GoToWin
from .grid import Grid
from .grid_search import GridSearch
from .grid_standart import GridStandart
from .img_view_win import ImgViewWin
from .info_win import InfoWin
from .path_bar import PathBar
from .search_bar import SearchBar
from .servers_win import ServersWin
from .settings_win import SettingsWin
from .sort_bar import SortBar
from .table_view import TableView
from .tags_menu import FiltersMenu
from .top_bar import TopBar
from .tree_menu import TreeMenu
from .warn_win import WinQuestion


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


class ScrollUpBtn(QLabel):
    clicked = pyqtSignal()
    arrow_up_sym = "\u25B2" # ▲
    border_radius = 20
    svg_size = 40

    def __init__(self, parent: QWidget):
        super().__init__(ScrollUpBtn.arrow_up_sym, parent)
        self.setFixedSize(ScrollUpBtn.svg_size, ScrollUpBtn.svg_size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"""
            background-color: {Static.GRAY_GLOBAL};
            border-radius: {ScrollUpBtn.border_radius}px;
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
    base_dir = os.path.expanduser("~/Downloads")
    splitter_handle_width = 12
    folders_text = "Папки"
    favs_text = "Избранное"
    new_win_offset = 20
    del_grid_timer = 3000
    scroll_up_width_offset = 70
    scroll_up_height_offset = 110
    first_load = True
    list_text = "Список"
    grid_text = "Плитка"
    attention = "Внимание"
    cache_download_descr ="Будет кэшировано все содержимое этой папки. Продолжить?"

    def __init__(self, dir: str = None):
        super().__init__()
        self.main_win_list: list[MainWin] = []
        self.search_item: SearchItem = SearchItem()
        self.main_win_item: MainWinItem = MainWinItem()
        self.sort_item: SortItem = SortItem()

        self.setMinimumSize(MainWin.min_width_, MainWin.min_height_)
        self.resize(MainWin.width_, MainWin.height_)
        self.setMenuBar(BarMacos())

        if MainWin.first_load:
            self.change_theme()
            MainWin.first_load = False

        if dir:
            self.main_win_item.main_dir = dir
        else:
            sys_vol = SharedUtils.get_sys_vol()
            dir = SharedUtils.add_sys_vol(MainWin.base_dir, sys_vol)
            self.main_win_item.main_dir = dir

        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.resize_timer_timeout)

        main_lay = QHBoxLayout()
        main_lay.setContentsMargins(5, 0, 5, 0)
        main_lay.setSpacing(0)
        self.setLayout(main_lay)

        self.splitter = QSplitter()
        self.splitter.setHandleWidth(MainWin.splitter_handle_width)
        main_lay.addWidget(self.splitter)


        self.left_wid = QSplitter()
        self.left_wid.setHandleWidth(MainWin.splitter_handle_width)
        self.left_wid.setOrientation(Qt.Orientation.Vertical)
        self.tabs_widget = TabsWidget()
        self.left_wid.addWidget(self.tabs_widget)
        self.tree_menu = TreeMenu(self.main_win_item)
        self.tabs_widget.addTab(self.tree_menu, MainWin.folders_text)
        self.favs_menu = FavsMenu(self.main_win_item)
        self.tabs_widget.addTab(self.favs_menu, MainWin.favs_text)

        self.filters_menu = FiltersMenu()
        self.left_wid.addWidget(self.filters_menu)
        
        self.left_wid.setSizes([999, 1])

        right_wid = QWidget()
        self.r_lay = QVBoxLayout()
        self.r_lay.setContentsMargins(0, 0, 0, 0)
        self.r_lay.setSpacing(0)
        right_wid.setLayout(self.r_lay)
        self.top_bar = TopBar(self.main_win_item, self.search_item)
        sep_one = USep()
        self.search_bar = SearchBar(self.search_item)
        self.search_bar_sep = USep()

        self.grid = Grid(self.main_win_item, False)
        Utils.fill_missing_methods(GridSearch, Grid)
        self.grid_spacer = QWidget()

        sep_two = USep()
        self.path_bar = PathBar(self.main_win_item)
        sep = USep()
        self.sort_bar = SortBar(self.sort_item, self.main_win_item)

        self.splitter.addWidget(self.left_wid)
        self.splitter.addWidget(right_wid)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([MainWin.left_menu_w, self.width() - MainWin.left_menu_w])

        self.top_bar.new_history_item(self.main_win_item.main_dir)
        self.path_bar.update(self.main_win_item.main_dir)
        self.sort_bar.sort_menu_update()
        self.tabs_widget.setCurrentIndex(1)

        self.scroll_up = ScrollUpBtn(self)
        self.scroll_up.clicked.connect(lambda: self.grid.verticalScrollBar().setValue(0))

        self.r_lay.insertWidget(0, self.top_bar)
        self.r_lay.insertWidget(1, sep_one)
        self.r_lay.insertWidget(2, self.search_bar)
        self.r_lay.insertWidget(3, self.search_bar_sep)
        self.r_lay.insertWidget(MainWin.grid_insert_num, self.grid)
        self.r_lay.insertWidget(5, self.grid_spacer)
        self.r_lay.insertWidget(6, sep_two)
        self.r_lay.insertWidget(7, self.path_bar)
        self.r_lay.insertWidget(8, sep)
        self.r_lay.insertWidget(9, self.sort_bar)

        self.setup_signals()
        self.load_st_grid()
        self.on_start()

        if not JsonData.favs:
            self.tabs_widget.setCurrentIndex(0)

    def on_start(self):
        self.clear_data = AutoCacheCleaner()
        UThreadPool.start(self.clear_data)

    def setup_signals(self):
        signal_map = {
            # splitter
            self.splitter.splitterMoved: lambda: self.resize_timer.start(MainWin.resize_ms),

            # tree_menu
            self.tree_menu.load_st_grid_sig: self.load_st_grid,
            self.tree_menu.add_fav: self.favs_menu.add_fav,
            self.tree_menu.del_fav: self.favs_menu.del_fav,
            self.tree_menu.new_history_item: self.top_bar.new_history_item,
            self.tree_menu.open_in_new_window: lambda d: self.open_in_new_win((d, None)),

            # favs_menu
            self.favs_menu.load_st_grid: self.load_st_grid,
            self.favs_menu.new_history_item: self.top_bar.new_history_item,
            self.favs_menu.open_in_new_win: lambda d: self.open_in_new_win((d, None)),

            # rating_menu
            self.filters_menu.filter_thumbs: lambda: (self.grid.filter_thumbs()),
            self.filters_menu.rearrange_thumbs: lambda: self.grid.rearrange_thumbs(),

            # top_bar
            self.top_bar.level_up: self.level_up,
            self.top_bar.change_view: self.change_view_cmd,
            self.top_bar.load_search_grid: self.load_search_grid,
            self.top_bar.load_st_grid: self.load_st_grid,
            self.top_bar.navigate: self.load_st_grid,
            self.top_bar.open_in_new_win: lambda d: self.open_in_new_win((d, None)),
            self.top_bar.open_settings: self.open_settings,
            self.top_bar.new_folder: self.new_folder,

            # search_bar
            self.search_bar.on_filter_clicked: self.load_search_grid,
            self.search_bar.on_pause_clicked: lambda v:self.grid.toggle_pause(v),
            self.search_bar.on_edit_clicked: self.top_bar.on_search_bar_clicked,
            self.search_bar.on_exit_clicked: self.load_st_grid,

            # path_bar
            self.path_bar.new_history_item: self.top_bar.new_history_item,
            self.path_bar.load_st_grid: self.load_st_grid,
            self.path_bar.info_win: self.open_info_win,
            self.path_bar.add_fav: self.favs_menu.add_fav,
            self.path_bar.del_fav: self.favs_menu.del_fav,

            # sort_bar
            self.sort_bar.resize_thumbs: lambda: self.grid.resize_thumbs(),
            self.sort_bar.rearrange_thumbs: lambda: self.grid.rearrange_thumbs(),
            self.sort_bar.sort_thumbs: lambda: self.grid.sort_thumbs(),
            self.sort_bar.load_st_grid: lambda: self.load_st_grid(),
            self.sort_bar.open_go_win: lambda: self.open_go_win(),
        }

        for signal, slot in signal_map.items():
            signal.connect(slot)

    def new_folder(self):
        if isinstance(self.grid, (GridStandart, TableView)):
            self.grid.new_folder()

    def change_theme(self):
        app: QApplication = QApplication.instance()
        if JsonData.dark_mode is None:
            app.setPalette(QPalette())
            app.setStyle("macintosh")
        elif JsonData.dark_mode:
            app.setPalette(UPallete.dark())
            app.setStyle("Fusion")
        else:
            app.setPalette(UPallete.light())
            app.setStyle("Fusion")
        
        if not MainWin.first_load:
            self.grid.reload_rubber()

    def open_img_view(self, data: dict):
        def closed():
            self.img_view_win = None
            gc.collect()

        def set_db_rating(data_tuple: tuple):
            rating, url = data_tuple
            wid = self.grid.url_to_wid.get(url)
            if not wid:
                return
            self.rating_task = RatingTask(self.main_win_item.main_dir, wid, rating)
            assert isinstance(self.rating_task, RatingTask)
            self.rating_task.sigs.finished_.connect(
                lambda: self.grid.set_thumb_rating(wid, rating)
            )
            UThreadPool.start(self.rating_task)

        self.img_view_win = ImgViewWin(
            data["start_url"], data["url_to_wid"], data["is_selection"]
        )

        # mapping сигнал → слот
        signal_map = {
            self.img_view_win.move_to_wid: self.grid.select_single_thumb,
            self.img_view_win.new_rating: set_db_rating,
            self.img_view_win.move_to_url: self.grid.select_path,
            self.img_view_win.closed: closed,
            self.img_view_win.info_win: self.open_info_win,
        }

        for signal, slot in signal_map.items():
            signal.connect(slot)

        self.img_view_win.center(self.window())
        self.img_view_win.show()

    def open_go_win(self):
        if JsonData.go_to_now:
            data = (0, Utils.read_from_clipboard())
            self.go_win_closed(data)
        else:
            self.go_win = GoToWin()
            self.go_win.closed.connect(self.go_win_closed)
            self.go_win.center(self)
            self.go_win.show()

    def go_win_closed(self, data: tuple[int, str]):
        """
        value: 0 = открыть путь в приложении, 1 = открыть путь к Finder
        """
        value, path = data
        self.path_finder_task = PathFinderTask(path)
        cmd = lambda path: self.path_finder_finished(value, path)
        self.path_finder_task.sigs.finished_.connect(cmd)
        UThreadPool.start(self.path_finder_task)

    def path_finder_finished(self, value: int, path: str):
        # 0 загрузить сетку, 1 показать через finder
        if path:
            if value == 0:
                if os.path.isdir(path):
                    self.main_win_item.main_dir = path
                else:
                    self.main_win_item.main_dir = os.path.dirname(path)
                    self.main_win_item.set_go_to(path)
                self.top_bar.new_history_item(self.main_win_item.main_dir)
                self.load_st_grid()
            elif value == 1:
                if os.path.isdir(path):
                    subprocess.Popen(["open", path])
                else:
                    subprocess.Popen(["open", "-R", path])

    def open_settings(self, *args):
        self.sett_win = SettingsWin()
        self.sett_win.show_texts_sig.connect(lambda: self.top_bar.toggle_texts())
        self.sett_win.load_st_grid.connect(self.load_st_grid)
        self.sett_win.theme_changed.connect(self.change_theme)
        self.sett_win.center(self)
        self.sett_win.show()

    def level_up(self):
        new_main_dir = os.path.dirname(self.main_win_item.main_dir)
        old_main_dir = self.main_win_item.main_dir

        if new_main_dir != os.sep:
            self.top_bar.new_history_item(new_main_dir)
            self.main_win_item.clear_urls_to_select()
            self.main_win_item.set_go_to(old_main_dir)
            self.main_win_item.main_dir = new_main_dir
            self.load_st_grid()

    def resize_timer_timeout(self):
        self.grid.resize_thumbs()
        self.grid.rearrange_thumbs()

    def open_in_new_win(self, data: tuple):
        new_main_dir, go_to = data
        new_win = MainWin(new_main_dir)
        self.main_win_list.append(new_win)
        x, y = self.window().x(), self.window().y()
        new_win.move(x + MainWin.new_win_offset, y + MainWin.new_win_offset)
        new_win.show()

    def setup_grid_signals(self):
        signal_map = {
            self.grid.download_cache: self.download_cache_task,
            self.grid.sort_menu_update: self.sort_bar.sort_menu_update,
            self.grid.total_count_update: self.sort_bar.sort_frame.set_total_text,
            self.grid.path_bar_update: self.path_bar.update,
            self.grid.add_fav: self.favs_menu.add_fav,
            self.grid.del_fav: self.favs_menu.del_fav,
            self.grid.move_slider: self.sort_bar.move_slider,
            self.grid.load_st_grid: self.load_st_grid,
            self.grid.open_in_new_win: self.open_in_new_win,
            self.grid.level_up: self.level_up,
            self.grid.new_history_item: self.top_bar.new_history_item,
            self.grid.change_view: self.change_view_cmd,
            self.grid.info_win: self.open_info_win,
            self.grid.img_view_win: self.open_img_view,
        }
        for signal, slot in signal_map.items():
            signal.connect(slot)
        self.grid.verticalScrollBar().valueChanged.connect(self.scroll_up_toggle)

    def load_search_grid(self):
        QTimer.singleShot(1500, lambda: self.top_bar.search_wid.setDisabled(False))
        self.grid.deleteLater()
        self.top_bar.search_wid.setDisabled(True)
        self.grid = GridSearch(
            self.main_win_item, self.sort_item, self.search_item, self, True
        )
        Utils.fill_missing_methods(TableView, Grid)
        self.grid.finished_.connect(self.search_bar.search_bar_search_fin)
        self.r_lay.insertWidget(MainWin.grid_insert_num, self.grid)
        self.search_bar.show()
        self.search_bar_sep.show()
        self.filters_menu.reset()
        self.scroll_up.hide()
        self.setup_grid_signals()
        QTimer.singleShot(100, self.grid.setFocus)

    def open_info_win(self, lst: list[BaseItem]):
        self.info_win = InfoWin(lst)
        self.info_win.center(self.img_view_win if self.img_view_win else self)
        self.info_win.show()
        
    def download_cache_task(self, dirs: list[str]):

        def open_win():
            self.cache_download_win = CacheDownloadWin(dirs)
            assert isinstance(self.cache_download_win, CacheDownloadWin)
            self.cache_download_win.center(self.window())
            QTimer.singleShot(10, self.cache_download_win.show)

        self.question_win = WinQuestion(
            self.attention,
            self.cache_download_descr
        )
        self.question_win.center(self.window())
        self.question_win.ok_clicked.connect(
            lambda: open_win()
        )
        self.question_win.ok_clicked.connect(
            lambda: self.question_win.deleteLater()
        )
        self.question_win.show()

    def disable_wids(self, value: bool):
        self.sort_bar.sort_frame.setDisabled(value)
        self.sort_bar.slider.setDisabled(value)
        self.filters_menu.setDisabled(value)

    def load_st_grid(self):
        self.grid_spacer.resize(0, self.height())
        self.grid_spacer.setFocus()
        self.grid.hide()
        QTimer.singleShot(100, self._load_st_grid)

    def _load_st_grid(self):
        if not os.path.exists(self.main_win_item.main_dir):
            slashed = self.main_win_item.main_dir.rstrip(os.sep)
            fixed_path = Utils.fix_path_prefix(slashed)
            if fixed_path:
                self.main_win_item.main_dir = fixed_path

        self.favs_menu.select_fav(self.main_win_item.main_dir)
        self.top_bar.search_wid.clear_search()
        self.search_bar.hide()
        self.search_bar_sep.hide()
        self.tree_menu.expand_path(self.main_win_item.main_dir)
        self.search_item.set_content(None)
        self.scroll_up.hide()
        self.grid.deleteLater()

        t = os.path.basename(self.main_win_item.main_dir)
        fav = JsonData.favs.get(self.main_win_item.main_dir, "")
        if fav and fav != t:
            t = f"{t} ({fav})"
        self.setWindowTitle(t)

        if self.main_win_item.get_view_mode() == 0:
            self.grid = GridStandart(self.main_win_item, False)
            Utils.fill_missing_methods(TableView, Grid)
            self.grid.setParent(self)
            self.grid.sort_item = self.sort_item
            self.grid.load_finder_items()
            self.disable_wids(False)

        elif self.main_win_item.get_view_mode() == 1:
            self.grid = TableView(self.main_win_item)
            Utils.fill_missing_methods(Grid, TableView)
            self.grid.setParent(self)
            self.grid.set_first_col_width()
            self.disable_wids(True)

        self.setup_grid_signals()
        self.r_lay.insertWidget(MainWin.grid_insert_num, self.grid)
        self.grid_spacer.resize(0, 0)
        QTimer.singleShot(100, lambda: self.grid.setFocus())

    def change_view_cmd(self):
        if self.main_win_item.get_view_mode() == 0:
            self.top_bar.change_view_btn.load(Static.INTERNAL_ICONS.get("grid.svg"))
            self.top_bar.change_view_btn.lbl.setText(self.grid_text)
            self.main_win_item.set_view_mode(1)

        else:
            self.top_bar.change_view_btn.load(Static.INTERNAL_ICONS.get("list.svg"))
            self.top_bar.change_view_btn.lbl.setText(self.list_text)
            self.main_win_item.set_view_mode(0)

        self.load_st_grid()

    def open_servers_win(self):
        self.servers_win = ServersWin()
        self.servers_win.center(self)
        self.servers_win.show()

    def scroll_up_toggle(self, value: int):
        if value == 0:
            self.scroll_up.hide()
        else:
            self.scroll_up.show()

    def on_exit(self):
        JsonData.write_config()
        os._exit(0)
    
    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        MainWin.width_ = self.geometry().width()
        MainWin.height_ = self.geometry().height()
        self.scroll_up.move(
            self.width() - MainWin.scroll_up_width_offset,
            self.height() - MainWin.scroll_up_height_offset
        )
        self.resize_timer.stop()
        self.resize_timer.start(MainWin.resize_ms)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        if len(WinBase.wins) > 1:
            self.deleteLater()
        else:
            self.hide()
            a0.ignore()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:  
        if a0.modifiers() == Qt.KeyboardModifier.ControlModifier:

            if a0.key() == Qt.Key.Key_F:
                self.top_bar.search_wid.setFocus()
                self.top_bar.search_wid.selectAll()

            elif a0.key() == Qt.Key.Key_W:
                self.close()
        
            elif a0.key() in (Qt.Key.Key_1, Qt.Key.Key_2):
                self.change_view_cmd()

            elif a0.key() == Qt.Key.Key_N:
                self.open_in_new_win((self.main_win_item.main_dir, None))
            
            elif a0.key() == Qt.Key.Key_K:
                self.open_servers_win()
        
        elif a0.key() == Qt.Key.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
                self.raise_()

        return super().keyPressEvent(a0)
