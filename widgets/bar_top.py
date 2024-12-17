import os

from PyQt5.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import (QAction, QHBoxLayout, QLabel, QMenu, QPushButton,
                             QTabBar, QVBoxLayout, QWidget)

from cfg import Dynamic, JsonData, Static
from signals import SignalsApp
from utils import Utils

from ._base import ULineEdit
from .win_settings import WinSettings


class ActionData:
    __slots__ = ["sort", "reversed", "text"]

    def __init__(self, sort: str | None, reversed: bool, text: str):
        self.sort: str | None = sort
        self.reversed: bool = reversed
        self.text: str = text


class ViewTypeBtn(QTabBar):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(90)

        self.addTab(Static.GRID_SYM * 3)
        self.addTab(Static.BURGER_SYM)

        self.setCurrentIndex(0)
        Dynamic.grid_view_type = 0

        self.tabBarClicked.connect(self.set_view_type_cmd)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            super().mousePressEvent(event)
        else:
            event.ignore()

    def set_view_type_cmd(self, index: int):
        self.setCurrentIndex(index)
        Dynamic.grid_view_type = index
        SignalsApp.all_.load_standart_grid.emit("")

    def tabSizeHint(self, index):
        size = QTabBar.tabSizeHint(self, index)
        return QSize(10, size.height())


class SearchWidget(QWidget):
    clear_search = pyqtSignal()

    def __init__(self):
        super().__init__()

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(0, 0, 0, 0)
        v_lay.setSpacing(0)
        self.setLayout(v_lay)

        self.search_wid = ULineEdit()
        self.search_wid.setPlaceholderText("Поиск")
        self.search_wid.setFixedWidth(170)
        self.search_wid.mouseDoubleClickEvent = self.show_templates
        self.search_wid.clear_btn_vcenter()
        v_lay.addWidget(self.search_wid)

        self.search_wid.textChanged.connect(self.on_text_changed)
        self.search_text: str = None

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(
            lambda: SignalsApp.all_.load_search_grid.emit(self.search_text)
            )
        
        self.clear_search.connect(self.costil)

        self.templates_menu = QMenu()

        data = {
            "Найти jpg": str((".jpg", ".jpeg", "jfif")),
            "Найти png": str((".png")),
            "Найти tiff": str((".tif", ".tiff")),
            "Найти psd/psb": str((".psd", ".psb")),
            "Найти raw": str((".nef", ".raw")),
            "Найти любые фото": str(Static.IMG_EXT)
            }

        for k, v in data.items():
            action = QAction(parent=self, text=k)
            action.triggered.connect(lambda e, xx=v: self.action_cmd(xx))
            self.templates_menu.addAction(action)

    def costil(self):
        self.search_wid.disconnect()
        self.search_wid.clear()
        self.search_wid.clear_btn.hide()
        self.search_wid.textChanged.connect(self.on_text_changed)

    def on_text_changed(self, text: str):
        self.search_timer.stop()
        if text:
            self.search_wid.clear_btn.show()
            self.search_text = text.strip()
            self.search_wid.setText(self.search_text)
            self.search_timer.start(1000)
        else:
            self.clear_search.emit()
            self.search_wid.clear_btn.hide()
            SignalsApp.all_.load_standart_grid.emit("")

    def show_templates(self, a0: QMouseEvent | None) -> None:
        self.templates_menu.exec(self.mapToGlobal(self.rect().bottomLeft()))
    
    def action_cmd(self, text: str):
        self.search_wid.setText(text)


class ColorLabel(QLabel):
    def __init__(self, text: str):
        super().__init__(text)
        self.is_selected = False


class FiltersBtn(QPushButton):
    def __init__(self):
        super().__init__(text=Static.STAR_SYM)
        
        self._menu = QWidget()
        self._menu.setWindowFlags(Qt.WindowType.Popup)

        self._menu.setLayout(QVBoxLayout())
        self._menu.layout().setContentsMargins(0, 0, 0, 0)
        self._menu.layout().setSpacing(1)

        # строчка с цветами

        self.color_wid = QWidget()
        self._menu.layout().addWidget(self.color_wid)
        color_lay = QHBoxLayout()
        color_lay.setContentsMargins(3, 3, 3, 3)
        color_lay.setSpacing(5)
        self.color_wid.setLayout(color_lay)

        self.enabled_filters = set()
        
        self.color_wids: list[ColorLabel] = []

        for color in Static.COLORS:
            label = ColorLabel(color)
            label.setFixedSize(20, 20)
            label.mousePressEvent = lambda e, w=label, c=color: self.toggle_color(w, c)
            color_lay.addWidget(label)
            self.color_wids.append(label)

        cancel_color = QLabel(Static.FILTERS_CROSS_SYM)
        cancel_color.setFixedSize(20, 20)
        cancel_color.mousePressEvent = self.reset_colors_cmd
        color_lay.addWidget(cancel_color)

        color_lay.addStretch(1)


        raging_wid = QWidget()
        self._menu.layout().addWidget(raging_wid)
        rating_lay = QHBoxLayout()
        rating_lay.setContentsMargins(3, 3, 3, 3)
        rating_lay.setSpacing(5)
        raging_wid.setLayout(rating_lay)

        self.rating_data = {1: False, 2: False,  3: False, 4: False, 5: False}
        self.rating_wids: list[QLabel] = []

        for rate in self.rating_data:
            label = QLabel(Static.STAR_SYM)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedSize(20, 20)
            label.mouseReleaseEvent = lambda e, r=rate: self.toggle_rating(r)
            rating_lay.addWidget(label)
            self.rating_wids.append(label)
        
        rating_lay.addStretch(1)

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            pont = self.rect().bottomLeft()
            self._menu.move(self.mapToGlobal(pont))
            self._menu.show()

    def style_btn(self, set_down=True, style=f"color: {Static.BLUE};"):

        if not self.enabled_filters:
            set_down = False
            style = ""

        self.setDown(set_down)
        self.setStyleSheet(style)

    def toggle_color(self, widget: ColorLabel, color: str):
        if widget.is_selected == True:
            self.enabled_filters.remove(widget)
            self.style_btn()
            Dynamic.color_filters.remove(color)
            widget.setStyleSheet("")
            widget.is_selected = False
        else:
            self.enabled_filters.add(widget)
            self.style_btn()
            Dynamic.color_filters.append(color)
            widget.setStyleSheet(f"background: {Static.BLUE};")
            widget.is_selected = True

        SignalsApp.all_.filter_grid.emit()

    def reset_colors_cmd(self, e):
        for wid in self.color_wids:
            wid.setStyleSheet("")
            wid.is_selected = False

        enabled_filters = []

        for i in self.enabled_filters:
            if isinstance(i, ColorLabel):
                enabled_filters.append(i)

        for i in enabled_filters:
                self.enabled_filters.remove(i)

        self.style_btn()

        Dynamic.color_filters.clear()
        SignalsApp.all_.filter_grid.emit()

    def toggle_rating(self, rate: int):
        if rate > 1:
            Dynamic.rating_filter = rate
            self.enabled_filters.add(0)
            self.style_btn()

            for i in self.rating_wids[:rate]:
                i.setStyleSheet(f"background: {Static.BLUE};")
            for i in self.rating_wids[rate:]:
                i.setStyleSheet("")
        else:

            if 0 in self.enabled_filters:
                self.enabled_filters.remove(0)

            self.style_btn()
            Dynamic.rating_filter = 0
            for i in self.rating_wids:
                i.setStyleSheet("")

        SignalsApp.all_.filter_grid.emit()

    def reset_filters(self):
        for i in self.rating_wids:
            i.setStyleSheet("")
        for i in self.color_wid.findChildren(QLabel):
            i.setStyleSheet("")
            i.is_selected = False

        Dynamic.color_filters.clear()
        Dynamic.rating_filter = 0
        self.enabled_filters.clear()
        self.style_btn()


class HistoryBtns(QWidget):
    clicked_ = pyqtSignal(int)

    def __init__(self):
        super().__init__()

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(0)

        back = QPushButton(Static.BACK_SYM)
        next = QPushButton(Static.NEXT_SYM)

        for i in (back, next):
            i.setFixedWidth(40)

        back.clicked.connect(lambda: self.clicked_.emit(-1))
        next.clicked.connect(lambda: self.clicked_.emit(1))

        h_lay.addWidget(back)
        h_lay.addWidget(next)

        self.setLayout(h_lay)


class BarTop(QWidget):

    def __init__(self):
        super().__init__()
        self.setFixedHeight(40)
        self.clmn = 0

        self.root: str = None
        self.history: list[str] = []
        self.index_: int = 0

        self.main_lay = QHBoxLayout()
        self.main_lay.setSpacing(10)
        self.main_lay.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_lay)

        self.history_btns = HistoryBtns()
        self.history_btns.clicked_.connect(self.navigate)
        self.main_lay.addWidget(self.history_btns)

        self.level_up_btn = QPushButton(Static.UP_CURVE)
        self.level_up_btn.setFixedWidth(50)
        self.level_up_btn.clicked.connect(self.level_up)
        self.main_lay.addWidget(self.level_up_btn)

        self.main_lay.addStretch()

  
        # чтобы кнопки смены вида (сетка или список)
        # стояли вровень с остальными кнопками  в баре
        # мы прибегаем в созданию родительского виджета и лейаута
        # для кнопок смены вида

        view_type_parent = QWidget()
        self.level_up_btn.adjustSize()
        level_up_h = self.level_up_btn.height()
        view_type_parent.setFixedHeight(level_up_h)
        self.main_lay.addWidget(view_type_parent)

        view_type_lay = QHBoxLayout()
        view_type_lay.setContentsMargins(0, 0, 0, 0)
        view_type_parent.setLayout(view_type_lay)

        self.view_type_btn = ViewTypeBtn()
        view_type_lay.addWidget(self.view_type_btn)


        self.filters_btn = FiltersBtn()
        self.main_lay.addWidget(self.filters_btn)

        self.sett_btn = QPushButton(parent=self, text=Static.GEAR_SYM)
        self.sett_btn.clicked.connect(self.open_settings_win)
        self.main_lay.addWidget(self.sett_btn)

        self.main_lay.addStretch()

        self.search_wid = SearchWidget()
        self.main_lay.addWidget(self.search_wid)

        SignalsApp.all_.new_history_item.connect(self.new_history)
        SignalsApp.all_.new_history_item.emit(JsonData.root)
        self.index_ -= 1

    def open_settings_win(self):
        self.win = WinSettings()
        Utils.center_win(Utils.get_main_win(), self.win)
        self.win.show()

    def new_history(self, root: str):
        if root == os.sep:
            return

        if len(self.history) > 100:
            self.history.pop(-1)

        self.history.append(root)
        self.index_ = len(self.history) - 1

    def navigate(self, offset: int):
        try:
            if self.index_ + offset in(-1, len(self.history)):
                return
            self.index_ += offset
            SignalsApp.all_.load_standart_grid.emit(self.history[self.index_])
        except (ValueError, IndexError):
            pass

    def level_up(self, e):
        root = os.path.dirname(JsonData.root)
        if not root == os.sep:
            SignalsApp.all_.new_history_item.emit(root)
            SignalsApp.all_.load_standart_grid.emit(root)