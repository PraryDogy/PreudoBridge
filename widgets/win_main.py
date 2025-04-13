import os

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QKeyEvent, QMouseEvent, QResizeEvent
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QApplication, QHBoxLayout, QLabel, QSplitter,
                             QTabWidget, QVBoxLayout, QWidget)

from cfg import Dynamic, JsonData, Static
from database import OrderItem
from utils import Utils
from widgets.bar_bottom import BarBottom
from widgets.bar_top import BarTop
from widgets.grid import Grid
from widgets.grid_list import GridList
from widgets.grid_search import GridSearch
from widgets.grid_standart import GridStandart
from widgets.menu_favs import MenuFavs
from widgets.menu_tags import MenuTags
from widgets.menu_tree import MenuTree
from widgets.win_img_view import LoadImage

ARROW_UP = "\u25B2" # ▲


class TabsWidget(QTabWidget):
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


class WinMain(QWidget):
    def __init__(self):
        super().__init__()

        self.main_dir = os.path.expanduser("~/Downloads")
        self.main_dir = Utils.add_system_volume(self.main_dir)

        # индекс 0 просмотр сеткой, индекс 1 просмотр списком
        self.view_index = 0

        self.setMinimumWidth(200)
        ww, hh = Dynamic.ww, Dynamic.hh
        self.resize(ww, hh)
        self.setMinimumSize(800, 500)
        
        self.resize_timer = QTimer(parent=self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.resize_timer_cmd)

        self.grid: Grid = Grid(self.main_dir, self.view_index)

        main_lay = QHBoxLayout()
        main_lay.setContentsMargins(5, 0, 5, 0)
        main_lay.setSpacing(0)
        self.setLayout(main_lay)

        splitter = QSplitter()
        splitter.splitterMoved.connect(lambda: self.resize_timer.start(500))
        main_lay.addWidget(splitter)

        left_wid = QWidget()
        splitter.addWidget(left_wid)
        left_v_lay = QVBoxLayout()
        left_v_lay.setContentsMargins(0, 0, 0, 5)
        left_v_lay.setSpacing(0)
        left_wid.setLayout(left_v_lay)

        self.menu_tabs = TabsWidget()
        left_v_lay.addWidget(self.menu_tabs)

        self.menu_tree = MenuTree()
        self.menu_tree.load_st_grid_sig.connect(self.load_st_grid_cmd)
        self.menu_tabs.addTab(self.menu_tree, "Папки")

        self.menu_favs = MenuFavs()
        self.menu_favs.init_ui(self.main_dir)
        self.menu_favs.init_ui_sig.connect(lambda: self.menu_favs.init_ui(self.main_dir))
        self.menu_favs.load_st_grid_sig.connect(self.load_st_grid_cmd)
        self.menu_tabs.addTab(self.menu_favs, "Избранное")
        self.menu_tree.fav_cmd_sig.connect(self.menu_favs.fav_cmd)

        show_hide_tags_btn = TagsBtn()
        show_hide_tags_btn.clicked_.connect(self.show_hide_tags)
        left_v_lay.addWidget(show_hide_tags_btn)

        self.menu_tags = MenuTags()
        self.menu_tags.filter_grid_sig.connect(lambda: self.grid.filter_())
        self.menu_tags.rearrange_grid_sig.connect(lambda: self.grid.rearrange())
        left_v_lay.addWidget(self.menu_tags)

        show_hide_tags_btn.click_cmd()

        self.menu_tabs.load_last_tab()

        right_wid = QWidget()
        splitter.addWidget(right_wid)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([Static.LEFT_MENU_W, self.width() - Static.LEFT_MENU_W])

        self.r_lay = QVBoxLayout()
        self.r_lay.setContentsMargins(0, 0, 0, 0)
        self.r_lay.setSpacing(0)
        right_wid.setLayout(self.r_lay)
        
        self.bar_top = BarTop()
        # перейти на директорию выше
        self.bar_top.level_up.connect(self.level_up_cmd)
        # изменить отображение сетка/список
        self.bar_top.change_view.connect(self.change_view_cmd)
        # начать поиск
        self.bar_top.start_search.connect(self.load_search_grid)
        # очистить поиск, загрузить стандартную сетку с текущей директорией
        self.bar_top.search_was_cleaned.connect(lambda: self.load_st_grid_cmd((self.main_dir, None)))
        # перейти вперед/назад по истории посещений
        self.bar_top.navigate.connect(lambda dir: self.load_st_grid_cmd((dir, None)))
        # в виджете поиска был выбран шаблон "Поиск по списку"
        # при открытиии окна Поиск по списку отображаем директорию
        # в которой будет произведен поиск
        # мы не можем сюда перенсти фунеционал целого окна list_win
        # проще постфактум установить текст для лейбла в этом окне
        self.bar_top.list_win_opened.connect(lambda: self.bar_top.set_path_list_win(self.main_dir))
        # было открыто окно настроек и был клик "очистить данные в этой папке"
        self.bar_top.clear_data_clicked.connect(self.clear_data_cmd)
        # добавляем текущую директорию в историю
        self.bar_top.new_history_item_cmd(self.main_dir)
        self.r_lay.insertWidget(0, self.bar_top)
        # после инициации bartop можем подключать сигналы, ссылающиеся на него
        self.menu_tree.new_history_item.connect(self.bar_top.new_history_item_cmd)
        self.menu_favs.new_history_item.connect(self.bar_top.new_history_item_cmd)
        
        self.bar_bottom = BarBottom()
        # устанавливаем изначальный путь в нижний бар
        self.bar_bottom.set_new_path(self.main_dir)
        self.bar_bottom.new_history_item.connect(self.bar_top.new_history_item_cmd)
        self.bar_bottom.load_st_grid_sig.connect(self.load_st_grid_cmd)
        self.bar_bottom.resize_grid_sig.connect(lambda: self.grid.resize_())
        self.bar_bottom.order_grid_sig.connect(lambda: self.grid.order_())
        self.bar_bottom.rearrange_grid_sig.connect(lambda: self.grid.rearrange())
        self.bar_bottom.open_path_sig.connect(self.open_path_cmd)
        self.bar_bottom.open_img_view.connect(self.open_img_view_cmd)
        self.r_lay.insertWidget(2, self.bar_bottom)

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
        # self.grid: Grid = Grid()
        self.load_st_grid_cmd((self.main_dir, None))

    def open_img_view_cmd(self, path: str):
        order_item = OrderItem(path, 0, 0, 0)
        self.grid.view_thumb_cmd(order_item)

    def clear_data_cmd(self):
        db = os.path.join(self.main_dir, Static.DB_FILENAME)
        if os.path.exists(db):
            os.remove(db)
            self.load_st_grid_cmd((self.main_dir, None))

    def level_up_cmd(self, *args):
        new_main_dir = os.path.dirname(self.main_dir)
        if new_main_dir != os.sep:
            self.load_st_grid_cmd((new_main_dir, None))
            self.bar_top.new_history_item_cmd(new_main_dir)
            self.main_dir = new_main_dir

    def change_view_cmd(self, index: int):
        self.view_index = index
        self.load_st_grid_cmd((self.main_dir, None))

    def resize_timer_cmd(self):
        self.grid.resize_()
        self.grid.rearrange()

    def show_hide_tags(self):
        if self.menu_tags.isHidden():
            self.menu_tags.show()
        else:
            self.menu_tags.hide()

    def open_path_cmd(self, filepath: str):
        if not os.path.exists(filepath):
            return

        if filepath.endswith(Static.IMG_EXT):
            self.main_dir = os.path.dirname(filepath)
            self.load_st_grid_cmd((self.main_dir, filepath))
        else:
            self.main_dir = filepath
            self.load_st_grid_cmd((self.main_dir, None))

    def load_search_grid(self, search_text: str):
        self.grid.close()
        self.menu_tags.reset()
        self.grid = GridSearch(self.main_dir, self.view_index, search_text, None)
        # нужно сразу добавлять в окно, чтобы у виджета появился родитель
        # тогда во всех эвентах правильно сработает self.grid.window()
        self.r_lay.insertWidget(1, self.grid)
        self.grid.bar_bottom_update.connect(self.bar_bottom.update_bar_cmd)
        self.grid.fav_cmd_sig.connect(self.menu_favs.fav_cmd)
        self.grid.move_slider_sig.connect(self.bar_bottom.slider.move_slider_cmd)
        self.grid.verticalScrollBar().valueChanged.connect(self.scroll_up_scroll_value)
        self.grid.setFocus()

    def load_any_grid(self, data: tuple):
        if isinstance(self.grid, GridSearch):
            self.grid.order_()
            self.grid.rearrange()
        else:
            self.load_st_grid_cmd(data)

    def load_st_grid_cmd(self, data: tuple):
        """
        new_main_dir (self.main_dir), path to widget for select widget
        """
        new_main_dir, path_for_select = data

        if new_main_dir:
            self.main_dir = new_main_dir

        LoadImage.cache.clear()
        self.grid.close()

        base_name = os.path.basename(self.main_dir)
        if self.main_dir in JsonData.favs:
            fav = JsonData.favs[self.main_dir]
            if fav != base_name:
                title = f"{base_name} ({JsonData.favs[self.main_dir]})"
            else:
                title = base_name
        else:
            title = base_name

        self.setWindowTitle(title)
        self.menu_favs.fav_cmd(("select", self.main_dir))

        # появляется рекурсия, нужна отладка
        # self.bar_top.search_wid.search_was_cleaned.emit()
        self.bar_top.search_wid.clear_without_signal()

        if self.view_index == 0:
            self.grid = GridStandart(self.main_dir, self.view_index, path_for_select)

        elif self.view_index == 1:
            self.grid = GridList(self.main_dir, self.view_index)

        # нужно сразу добавлять в окно, чтобы у виджета появился родитель
        # тогда во всех эвентах правильно сработает self.grid.window()
        self.r_lay.insertWidget(1, self.grid)

        self.grid.new_history_item.connect(self.bar_top.new_history_item_cmd)
        self.grid.bar_bottom_update.connect(self.bar_bottom.update_bar_cmd)
        self.grid.fav_cmd_sig.connect(self.menu_favs.fav_cmd)
        self.grid.load_st_grid_sig.connect(self.load_st_grid_cmd)
        self.grid.move_slider_sig.connect(self.bar_bottom.slider.move_slider_cmd)
        self.grid.change_view_sig.connect(self.change_view_cmd)

        self.grid.verticalScrollBar().valueChanged.connect(
            self.scroll_up_scroll_value
        )

        self.menu_tree.expand_path(self.main_dir)
        self.grid.setFocus()
        self.window().raise_()

    def scroll_up_scroll_value(self, value: int):
        if value == 0:
            self.scroll_up.hide()
        else:
            self.scroll_up.show()
    
    def user_exit(self):

        # предотвращает segmentation fault

        wids = (
            self.scroll_up,
            self.menu_favs,
            self.menu_tree,
            self.menu_tabs,
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
        self.resize_timer.start(100)

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
                active_win = QApplication.activeWindow()
                wins = [
                    i
                    for i in QApplication.topLevelWidgets()
                    if isinstance(i, WinMain)
                ]

                if len(wins) > 1:
                    active_win.deleteLater()
                else:
                    self.hide()

                wins = [
                    i
                    for i in QApplication.topLevelWidgets()
                    if isinstance(i, WinMain)
                ]

            elif a0.key() == Qt.Key.Key_Q:
                QApplication.instance().quit()
        
            elif a0.key() == Qt.Key.Key_1:
                self.change_view_cmd(0)
            
            elif a0.key() == Qt.Key.Key_2:
                self.change_view_cmd(1)

        elif a0.key() == Qt.Key.Key_Escape:
            self.setFocus()

        return super().keyPressEvent(a0)
