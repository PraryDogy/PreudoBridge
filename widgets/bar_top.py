import os

from PyQt5.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import (QAction, QFrame, QGridLayout, QHBoxLayout, QLabel,
                             QMenu, QPushButton, QSpacerItem, QTabBar,
                             QTabWidget, QVBoxLayout, QWidget)

from cfg import (BACK_SYM, BLUE, BURGER_SYM, COLORS, FAT_DOT_SYM,
                 FILTERS_CROSS_SYM, GRID_SYM, IMG_EXT, NEXT_SYM,
                 SEARCH_CROSS_SYM, STAR_SYM, UP_CURVE, Dynamic, JsonData)
from database import ORDER
from signals import SignalsApp
from utils import Utils

from ._base import ULineEdit
from .win_settings import WinSettings

SETT_SYM = "\U00002699"


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

        self.addTab(GRID_SYM * 3)
        self.addTab(BURGER_SYM)

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

        self.input_wid = ULineEdit()
        self.input_wid.setPlaceholderText("Поиск")
        self.input_wid.setStyleSheet("padding-left: 2px; padding-right: 20px;")
        self.input_wid.setFixedSize(170, 25)
        self.input_wid.mouseDoubleClickEvent = self.show_templates
        v_lay.addWidget(self.input_wid)

        self.clear_btn = QLabel(parent=self, text=SEARCH_CROSS_SYM)
        self.clear_btn.setFixedSize(15, 10)
        self.clear_btn.move(self.input_wid.width() - 20, 8)
        self.clear_btn.hide()
        self.clear_btn.mouseReleaseEvent = lambda e: self.input_wid.clear()

        self.input_wid.textChanged.connect(self.on_text_changed)
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
            "Найти любые фото": str(IMG_EXT)
            }

        for k, v in data.items():
            action = QAction(parent=self, text=k)
            action.triggered.connect(lambda e, xx=v: self.action_cmd(xx))
            self.templates_menu.addAction(action)

    def costil(self):
        self.input_wid.disconnect()
        self.input_wid.clear()
        self.clear_btn.hide()
        self.input_wid.textChanged.connect(self.on_text_changed)

    def on_text_changed(self, text: str):
        self.search_timer.stop()
        if text:
            self.clear_btn.show()
            self.search_text = text.strip()
            self.input_wid.setText(self.search_text)
            self.search_timer.start(1000)
        else:
            self.clear_search.emit()
            self.clear_btn.hide()
            SignalsApp.all_.load_standart_grid.emit("")

    def show_templates(self, a0: QMouseEvent | None) -> None:
        self.templates_menu.exec(self.mapToGlobal(self.rect().bottomLeft()))
    
    def action_cmd(self, text: str):
        self.input_wid.setText(text)


class ColorLabel(QLabel):
    def __init__(self, text: str):
        super().__init__(text)
        self.is_selected = False


class FiltersBtn(QPushButton):
    def __init__(self):
        super().__init__(text=FAT_DOT_SYM)
        
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

        for color in COLORS:
            label = ColorLabel(color)
            label.setFixedSize(20, 20)
            label.mousePressEvent = lambda e, w=label, c=color: self.toggle_color(w, c)
            color_lay.addWidget(label)
            self.color_wids.append(label)

        cancel_color = QLabel(FILTERS_CROSS_SYM)
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
            label = QLabel(STAR_SYM)
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

    def style_btn(self, set_down=True, style=f"color: {BLUE};"):

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
            widget.setStyleSheet(f"background: {BLUE};")
            widget.is_selected = True

        SignalsApp.all_.filter_grid.emit()

    def reset_colors_cmd(self, e):
        for wid in self.color_wids:
            wid.setStyleSheet("")
            wid.is_selected = False

        for i in self.enabled_filters:
            if isinstance(i, ColorLabel):
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
                i.setStyleSheet(f"background: {BLUE};")
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


class HistoryBtns(QTabBar):
    clicked_ = pyqtSignal(int)

    def __init__(self):
        super().__init__()

        self.addTab(BACK_SYM)

        self.addTab("")
        self.setTabVisible(1, False)

        self.addTab(NEXT_SYM)
        self.fake_click()

        self.tabBarClicked.connect(self.cmd_)

    def fake_click(self):
        self.setCurrentIndex(1)

    def cmd_(self, *args):
        if args[0] == 1:
            self.clicked_.emit(-1)
        else:
            self.clicked_.emit(1)

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        QTimer.singleShot(100, self.fake_click)
        return super().mouseReleaseEvent(a0)


class BarTop(QFrame):

    def __init__(self):
        super().__init__()
        self.setFixedHeight(40)
        self.clmn = 0

        self.root: str = None
        self.history: list[str] = []
        self.index_: int = 0

        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(10)
        self.grid_layout.setContentsMargins(5, 0, 0, 0)
        self.setLayout(self.grid_layout)

        self.clmn += 1
        self.history_btns = HistoryBtns()
        self.history_btns.clicked_.connect(self.navigate)
        self.grid_layout.addWidget(self.history_btns, 0, self.clmn)

        self.clmn += 1
        self.level_up_btn = QPushButton(UP_CURVE)
        self.level_up_btn.setFixedWidth(50)
        self.level_up_btn.clicked.connect(self.level_up)
        self.grid_layout.addWidget(self.level_up_btn, 0, self.clmn)

        self.clmn += 1
        self.grid_layout.setColumnStretch(self.clmn, 10)
        self.grid_layout.addItem(QSpacerItem(1, 1), 0, self.clmn)

        self.clmn += 1
        self.grid_view_type_btn = ViewTypeBtn()
        self.grid_layout.addWidget(self.grid_view_type_btn, 0, self.clmn)

        self.clmn += 1
        self.filters_btn = FiltersBtn()
        self.grid_layout.addWidget(self.filters_btn, 0, self.clmn)

        self.clmn += 1
        self.sett_btn = QPushButton(parent=self, text=SETT_SYM)
        self.sett_btn.clicked.connect(self.open_settings_win)
        self.grid_layout.addWidget(self.sett_btn, 0, self.clmn)

        self.clmn += 1
        self.grid_layout.setColumnStretch(self.clmn, 10)
        self.grid_layout.addItem(QSpacerItem(1, 1), 0, self.clmn)

        self.clmn += 1
        self.search_wid = SearchWidget()
        self.grid_layout.addWidget(self.search_wid, 0, self.clmn)

        SignalsApp.all_.new_history.connect(self.new_history)
        SignalsApp.all_.new_history.emit(JsonData.root)
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
            SignalsApp.all_.new_history.emit(root)
            SignalsApp.all_.load_standart_grid.emit(root)