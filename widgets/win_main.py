import gc
import os
import re
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import (QCloseEvent, QKeyEvent, QMouseEvent, QPalette,
                         QResizeEvent)
from PyQt5.QtWidgets import (QApplication, QHBoxLayout, QLabel, QSplitter,
                             QTabWidget, QVBoxLayout, QWidget)

from cfg import Dynamic, JsonData, Static
from system.items import (ClipboardItem, DataItem, MainWinItem, SearchItem,
                          SortItem)
from system.paletes import UPallete
from system.shared_utils import SharedUtils, ImgUtils
from system.utils import Utils

from ._base_widgets import USep, WinBase
from .bar_macos import BarMacos
from .bar_path import BarPath
from .bar_sort import BarSort
from .bar_top import BarTop
from .grid import Grid
from .grid_search import GridSearch
from .grid_standart import GridStandart
from .menu_favs import MenuFavs
from .menu_filters import MenuFilters
from .menu_tree import MenuTree
from .table_view import TableView
from .win_copy_files import WinCopyFiles
from .win_go_to import WinGoTo
from .win_img_view import WinImgView
from .win_info import WinInfo
from .win_servers import WinServers
from .win_settings import WinSettings
from .win_warn import WinWarn


class TreeFavsWid(QTabWidget):
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
            background-color: rgba(128, 128, 128, 0.3);
            border-radius: {ScrollUpBtn.border_radius}px;
            """
            )
        
    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        return super().mouseReleaseEvent(ev)


class WinMain(WinBase):
    resize_ms = 100
    grid_index = 3
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
    search_text = "Идет поиск"
    search_fin_text = "Поиск завершен"
    cache_download_descr ="Будет кэшировано все содержимое этой папки. Продолжить?"

    def __init__(self, dir: str = base_dir):
        super().__init__()
        self.setMinimumSize(WinMain.min_width_, WinMain.min_height_)
        self.resize(Static.base_ww, Static.base_hh)
    
        self.main_win_list: list[WinMain] = []
        self.search_item = SearchItem()
        self.sort_item = SortItem()
        self.img_view_win = None

        self.main_win_item = MainWinItem()
        self.main_win_item.set_current_dir(dir)

        if WinMain.first_load:
            self.change_theme()
            WinMain.first_load = False

        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.resize_timer_timeout)

        # --- Меню и панель ---
        self.bar_macos = BarMacos()
        self.bar_macos.new_win.connect(
            lambda: self.open_in_new_win((self.base_dir, None))
        )
        self.bar_macos.servers_win.connect(self.open_servers_win)
        self.bar_macos.settings_win.connect(self.open_settings)
        self.bar_macos.go_to_win.connect(self.go_to_win)
        self.setMenuBar(self.bar_macos)

        # --- Основной layout ---
        main_lay = QHBoxLayout()
        main_lay.setContentsMargins(5, 0, 5, 0)
        main_lay.setSpacing(0)
        self.centralWidget().setLayout(main_lay)

        # --- Левый виджет ---
        left_side_widget = QSplitter()
        left_side_widget.setHandleWidth(WinMain.splitter_handle_width)
        left_side_widget.setOrientation(Qt.Orientation.Vertical)
        left_side_widget.setContentsMargins(0, 0, 0, 5)

        tree_favs_wid = TreeFavsWid()

        self.menu_tree = MenuTree(self.main_win_item)
        tree_favs_wid.addTab(self.menu_tree, WinMain.folders_text)

        self.menu_favs = MenuFavs(self.main_win_item)
        tree_favs_wid.addTab(self.menu_favs, WinMain.favs_text)
        left_side_widget.addWidget(tree_favs_wid)

        tree_favs_wid.setCurrentIndex(1)

        self.menu_filters = MenuFilters()
        left_side_widget.addWidget(self.menu_filters)
        left_side_widget.setSizes([
            self.min_height_ - 120,
            120
        ])

        # --- Правый виджет ---
        right_side_widget = QWidget()
        self.right_side_layout = QVBoxLayout()
        right_side_widget.setLayout(self.right_side_layout)
        self.right_side_layout.setContentsMargins(0, 0, 0, 0)
        self.right_side_layout.setSpacing(0)

        self.bar_top = BarTop(self.main_win_item, self.search_item)
        self.bar_top.new_history_item(dir)
        self.right_side_layout.insertWidget(0, self.bar_top)
        self.right_side_layout.insertWidget(1, USep())

        self.grid = Grid(self.main_win_item, False)
        Utils.fill_missing_methods(GridSearch, Grid)
        self.right_side_layout.insertWidget(WinMain.grid_index, self.grid)
        self.right_side_layout.insertWidget(4, USep())

        self.bar_path = BarPath(self.main_win_item)
        self.bar_path.update(dir)
        self.right_side_layout.insertWidget(5, self.bar_path)
        self.right_side_layout.insertWidget(6, USep())

        self.bar_sort = BarSort(self.sort_item, self.main_win_item)
        self.bar_sort.sort_menu_update()
        self.right_side_layout.insertWidget(7, self.bar_sort)

        self.main_splitter = QSplitter()
        self.main_splitter.setHandleWidth(WinMain.splitter_handle_width)
        self.main_splitter.addWidget(left_side_widget)
        self.main_splitter.addWidget(right_side_widget)
        self.main_splitter.setSizes([
            WinMain.left_menu_w,
             self.width() - WinMain.left_menu_w
        ])
        self.main_splitter.setContentsMargins(0, 5, 0, 0)
        main_lay.addWidget(self.main_splitter)

        # --- ScrollUp кнопка ---
        self.scroll_up = ScrollUpBtn(self)
        self.scroll_up.clicked.connect(
            lambda: self.grid.verticalScrollBar().setValue(0)
        )

        self.setup_signals()
        self.load_st_grid(dir)

    def setup_signals(self):
        # splitter
        self.main_splitter.splitterMoved.connect(lambda: self.resize_timer.start(WinMain.resize_ms))

        # tree_menu
        self.menu_tree.load_st_grid_sig.connect(self.load_st_grid)
        self.menu_tree.add_fav.connect(self.menu_favs.add_fav)
        self.menu_tree.del_fav.connect(self.menu_favs.del_fav)
        self.menu_tree.new_history_item.connect(self.bar_top.new_history_item)
        self.menu_tree.open_in_new_window.connect(self.open_in_new_win)

        # favs_menu
        self.menu_favs.load_st_grid.connect(self.load_st_grid)
        self.menu_favs.new_history_item.connect(self.bar_top.new_history_item)
        self.menu_favs.open_in_new_win.connect(self.open_in_new_win)

        self.menu_filters.filter_thumbs.connect(lambda: self.grid.filter_thumbs())
        self.menu_filters.rearrange_thumbs.connect(lambda: self.grid.rearrange_thumbs())

        # top_bar
        self.bar_top.level_up.connect(self.level_up)
        self.bar_top.change_view.connect(self.change_view_cmd)
        self.bar_top.load_search_grid.connect(self.load_search_grid)
        self.bar_top.load_st_grid.connect(self.load_st_grid)
        self.bar_top.open_in_new_win.connect(self.open_in_new_win)
        self.bar_top.open_settings.connect(self.open_settings)
        self.bar_top.new_folder.connect(self.new_folder)

        # path_bar
        self.bar_path.new_history_item.connect(self.bar_top.new_history_item)
        self.bar_path.load_st_grid.connect(self.load_st_grid)
        self.bar_path.info_win.connect(self.open_info_win)
        self.bar_path.add_fav.connect(self.menu_favs.add_fav)
        self.bar_path.del_fav.connect(self.menu_favs.del_fav)

        # sort_bar
        self.bar_sort.resize_thumbs.connect(lambda: self.grid.resize_thumbs())
        self.bar_sort.rearrange_thumbs.connect(lambda: self.grid.rearrange_thumbs())
        self.bar_sort.sort_thumbs.connect(lambda: self.grid.sort_thumbs())
        self.bar_sort.open_go_win.connect(lambda: self.go_to_toggle())

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
        
        if not WinMain.first_load:
            self.grid.reload_rubber()

    def open_img_view(self, data: dict):
        def closed():
            self.img_view_win = None
            gc.collect()

        self.img_view_win = WinImgView(
            data["start_url"], data["url_to_wid"], data["is_selection"]
        )

        self.img_view_win.move_to_wid.connect(self.grid.select_single_thumb)
        self.img_view_win.move_to_url.connect(self.grid.select_path)
        self.img_view_win.closed.connect(closed)
        self.img_view_win.info_win.connect(self.open_info_win)

        if WinImgView.ww == 0:
            self.img_view_win.resize(Static.base_ww, Static.base_hh)
            self.img_view_win.center(self.window())
            
        else:
            self.img_view_win.resize(WinImgView.ww, WinImgView.hh)
            self.img_view_win.move(WinImgView.xx, WinImgView.yy)

        self.img_view_win.show()

    def go_to_win(self):
        self.go_win = WinGoTo()
        self.go_win.closed.connect(self.go_to_cmd)
        self.go_win.center(self)
        self.go_win.show()

    def go_to_toggle(self):
        if JsonData.go_to_now:
            self.go_to_cmd(Utils.read_from_clipboard())
        else:
            self.go_to_win()

    def go_to_cmd(self, user_path: str):

        def finalize(path: str):
            if os.path.isdir(path):
                self.load_st_grid(path)
            elif path.endswith(ImgUtils.ext_all):
                self.main_win_item.go_to = path
                self.load_st_grid(os.path.dirname(path))

        user_path = user_path.strip("\"\'\n ")
        template = r"^(\/[^/]+)+\/?$"
        if not bool(re.fullmatch(template, user_path)):
            return
        if not os.path.exists(user_path):
            fixed_path = self.main_win_item.fix_path(user_path)
            if fixed_path:
                finalize(fixed_path)
        else:
            finalize(user_path)

    def open_settings(self, *args):
        self.sett_win = WinSettings()
        self.sett_win.show_texts_sig.connect(lambda: self.bar_top.toggle_texts())
        self.sett_win.theme_changed.connect(lambda: QTimer.singleShot(100, self.change_theme))
        self.sett_win.center(self)
        self.sett_win.show()

    def level_up(self):
        new_main_dir = os.path.dirname(self.main_win_item.abs_current_dir)
        old_main_dir = self.main_win_item.abs_current_dir

        if new_main_dir != os.sep:
            self.bar_top.new_history_item(new_main_dir)
            self.main_win_item.urls_to_select.clear()
            self.main_win_item.go_to = old_main_dir
            self.load_st_grid(new_main_dir)

    def resize_timer_timeout(self):
        self.grid.resize_thumbs()
        self.grid.rearrange_thumbs()

    def open_in_new_win(self, path: str):
        new_win = WinMain(path)
        self.main_win_list.append(new_win)
        x, y = self.window().x(), self.window().y()
        new_win.move(x + WinMain.new_win_offset, y + WinMain.new_win_offset)
        new_win.show()

    def setup_grid_signals(self):
        self.grid.sort_menu_update.connect(self.bar_sort.sort_menu_update)
        self.grid.total_count_update.connect(self.bar_sort.sort_frame.set_total_text)
        self.grid.path_bar_update.connect(self.bar_path.update)
        self.grid.add_fav.connect(self.menu_favs.add_fav)
        self.grid.del_fav.connect(self.menu_favs.del_fav)
        self.grid.move_slider.connect(self.bar_sort.move_slider)
        self.grid.load_st_grid.connect(self.load_st_grid)
        self.grid.open_in_new_win.connect(self.open_in_new_win)
        self.grid.go_to_widget.connect(self.go_to_cmd)
        self.grid.level_up.connect(self.level_up)
        self.grid.new_history_item.connect(self.bar_top.new_history_item)
        self.grid.change_view.connect(self.change_view_cmd)
        self.grid.info_win.connect(self.open_info_win)
        self.grid.img_view_win.connect(self.open_img_view)
        self.grid.paste_files.connect(self.paste_files)
        self.grid.verticalScrollBar().valueChanged.connect(self.scroll_up_toggle)

    def load_search_grid(self):
        QTimer.singleShot(
            1500,
            lambda: self.bar_top.search_wid.setDisabled(False)
        )
        self.bar_top.search_wid.setDisabled(True)
        self.grid.deleteLater()
        self.grid = GridSearch(
            main_win_item=self.main_win_item,
            sort_item=self.sort_item,
            search_item=self.search_item,
            parent=self,
            is_grid_search=True,
        )
        self.setWindowTitle(self.search_text)
        Utils.fill_missing_methods(TableView, Grid)
        self.right_side_layout.insertWidget(WinMain.grid_index, self.grid)
        self.scroll_up.hide()
        self.setup_grid_signals()
        self.grid.finished_.connect(
            lambda: self.setWindowTitle(self.search_fin_text)
        )
        QTimer.singleShot(100, self.grid.setFocus)

    def open_info_win(self, data_items: list[DataItem]):
        self.info_win = WinInfo(data_items)
        self.info_win.center(self.img_view_win if self.img_view_win else self)
        self.info_win.show()
        
    def paste_files(self):
        ClipboardItem.set_dest(self.main_win_item.abs_current_dir)
        self.win_copy = WinCopyFiles()
        self.win_copy.center(self.window())
        self.win_copy.show()
        QTimer.singleShot(300, self.win_copy.raise_)

    def disable_wids(self, value: bool):
        self.bar_sort.sort_frame.setDisabled(value)
        self.bar_sort.slider.setDisabled(value)
        self.menu_filters.setDisabled(value)

    def load_st_grid(self, path: str):

        def _load():
            self.bar_top.search_wid.clear_search()
            self.search_item.search_list.clear()
            self.scroll_up.hide()
            self.grid.deleteLater()

            self.setWindowTitle(os.path.basename(path))
            self.menu_favs.select_fav(path)
            self.menu_tree.expand_path(path)
            self.grid.deleteLater()

            if self.main_win_item.get_view_mode() == 0:
                self.grid = GridStandart(self.main_win_item, False)
                self.grid.load_finished.connect(self.grid.grid_wid.show)
                self.grid.load_finished.connect(self.grid.setFocus)
                self.grid.grid_wid.hide()
                classes = (TableView, Grid)
                self.grid.sort_item = self.sort_item
                self.disable_wids(False)
                self.grid.start_dir_scaner()

            elif self.main_win_item.get_view_mode() == 1:
                self.grid = TableView(self.main_win_item)
                self.grid.load_finished.connect(self.grid.show)
                self.grid.load_finished.connect(self.grid.setFocus)
                classes = (Grid, TableView)
                self.disable_wids(True)

            Utils.fill_missing_methods(*classes)
            self.setup_grid_signals()
            self.right_side_layout.insertWidget(WinMain.grid_index, self.grid)

        def _show_win(win: WinWarn):
            win.center(self.window())
            win.show()

        result = self.main_win_item.set_current_dir(path)
        if result:
            self.grid.grid_wid.hide()
            QTimer.singleShot(100, _load)
        else:
            no_conn = (
                "Такой папки не существует."
                "\nВозможно не подключен сетевой диск."
            )
            self.no_path_win = WinWarn(no_conn)
            QTimer.singleShot(100, lambda: _show_win(self.no_path_win))

    def change_view_cmd(self):
        if self.main_win_item.get_view_mode() == 0:
            self.bar_top.change_view_btn.load(
                os.path.join(Static.internal_images_dir, "grid.svg")
            )
            self.bar_top.change_view_btn.lbl.setText(self.grid_text)
            self.main_win_item.set_view_mode(1)

        else:
            self.bar_top.change_view_btn.load(
                os.path.join(Static.internal_images_dir, "list.svg")
            )
            self.bar_top.change_view_btn.lbl.setText(self.list_text)
            self.main_win_item.set_view_mode(0)

        self.load_st_grid(self.main_win_item.abs_current_dir)

    def open_servers_win(self):
        self.servers_win = WinServers()
        self.servers_win.center(self)
        self.servers_win.show()

    def scroll_up_toggle(self, value: int):
        if value == 0:
            self.scroll_up.hide()
        else:
            self.scroll_up.show()

    def on_exit(self):
        self.grid.deleteLater()
        JsonData.write_json_data()
        SharedUtils.exit_force()
    
    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        self.scroll_up.move(
            self.width() - WinMain.scroll_up_width_offset,
            self.height() - WinMain.scroll_up_height_offset
        )
        self.resize_timer.stop()
        self.resize_timer.start(WinMain.resize_ms)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        if len(WinBase.wins) > 1:
            self.deleteLater()
        else:
            self.hide()
            a0.ignore()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:  
        if a0.modifiers() == Qt.KeyboardModifier.ControlModifier:

            if a0.key() == Qt.Key.Key_F:
                self.bar_top.search_wid.setFocus()
                self.bar_top.search_wid.selectAll()

            elif a0.key() == Qt.Key.Key_W:
                self.close()
        
            elif a0.key() in (Qt.Key.Key_1, Qt.Key.Key_2):
                self.change_view_cmd()

            elif a0.key() == Qt.Key.Key_N:
                self.open_in_new_win(self.base_dir)
            
            elif a0.key() == Qt.Key.Key_K:
                self.open_servers_win()
        
        elif a0.key() == Qt.Key.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
                self.raise_()

        return super().keyPressEvent(a0)
