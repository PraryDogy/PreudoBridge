import os

from PyQt5.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import (QAction, QFrame, QGridLayout, QHBoxLayout, QLabel,
                             QLineEdit, QMenu, QPushButton, QSpacerItem,
                             QTabBar, QVBoxLayout, QWidget)

from cfg import (BACK_SYM, BLUE, BURGER_SYM, COLORS, FAT_DOT_SYM,
                 FILTERS_CROSS_SYM, GRID_SYM, IMG_EXT, NEXT_SYM,
                 SEARCH_CROSS_SYM, STAR_SYM, UP_CURVE, Dymanic, JsonData)
from database import ORDER
from signals import SignalsApp
from utils import Utils

from .win_settings import WinSettings

SETT_SYM = "\U00002699"


class ActionData:
    __slots__ = ["sort", "reversed", "text"]

    def __init__(self, sort: str | None, reversed: bool, text: str):
        self.sort: str | None = sort
        self.reversed: bool = reversed
        self.text: str = text


class SortTypeBtn(QPushButton):
    def __init__(self, parent: QWidget):
        super().__init__()
        self.setFixedWidth(105)
        self.setStyleSheet("text-align: center;")

        data_actions = (
            ActionData(None, False, "По возрастанию"),
            *(
            ActionData(sort=order_key, reversed=False, text=f"{order_dict.get('text')} \U00002191")
            for order_key, order_dict in ORDER.items()
            ),
            ActionData(None, True, "По убыванию"),
            *(
            ActionData(sort=order_key, reversed=True, text=f"{order_dict.get('text')} \U00002193")
            for order_key, order_dict in ORDER.items()
            )
            )

        menu = QMenu()
        self.setMenu(menu)

        for data_action in data_actions:
            action = QAction(parent=self, text=data_action.text)
            action.triggered.connect(lambda e, d=data_action: self._action_clicked(d))

            if data_action.sort == None:
                action.setDisabled(True)

            if data_action.sort == JsonData.sort:
                if data_action.reversed == JsonData.reversed:
                    self.setText(data_action.text)

            menu.addAction(action)

    def _action_clicked(self, data_action: ActionData):
        JsonData.sort = data_action.sort
        JsonData.reversed = data_action.reversed
        self.setText(data_action.text)
        SignalsApp.all.sort_grid.emit()


class ViewTypeBtn(QTabBar):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(90)

        self.addTab(GRID_SYM * 3)
        self.addTab(BURGER_SYM)

        if JsonData.list_view:
            self.setCurrentIndex(1)
        else:
            self.setCurrentIndex(0)

        self.tabBarClicked.connect(self.set_view_cmd)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            super().mousePressEvent(event)
        else:
            event.ignore()

    def set_view_cmd(self, index: int):
        if index == 0:
            self.setCurrentIndex(0)
            JsonData.list_view = False
        else:
            self.setCurrentIndex(1)
            JsonData.list_view = True
        SignalsApp.all.load_standart_grid.emit("")

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

        self.input_wid = QLineEdit()
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
            lambda: SignalsApp.all.load_search_grid.emit(self.search_text)
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
            SignalsApp.all.load_standart_grid.emit("")

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
            Dymanic.color_filters.remove(color)
            widget.setStyleSheet("")
            widget.is_selected = False
        else:
            self.enabled_filters.add(widget)
            self.style_btn()
            Dymanic.color_filters.append(color)
            widget.setStyleSheet(f"background: {BLUE};")
            widget.is_selected = True

        SignalsApp.all.filter_grid.emit()

    def reset_colors_cmd(self, e):
        for wid in self.color_wids:
            wid.setStyleSheet("")
            wid.is_selected = False

        for i in self.enabled_filters:
            if isinstance(i, ColorLabel):
                self.enabled_filters.remove(i)

        self.style_btn()

        Dymanic.color_filters.clear()
        SignalsApp.all.filter_grid.emit()

    def toggle_rating(self, rate: int):
        if rate > 1:
            Dymanic.rating_filter = rate
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
            Dymanic.rating_filter = 0
            for i in self.rating_wids:
                i.setStyleSheet("")

        SignalsApp.all.filter_grid.emit()

    def reset_filters(self):
        for i in self.rating_wids:
            i.setStyleSheet("")
        for i in self.color_wid.findChildren(QLabel):
            i.setStyleSheet("")
            i.is_selected = False

        Dymanic.color_filters.clear()
        Dymanic.rating_filter = 0
        self.enabled_filters.clear()
        self.style_btn()


class HistoryBtn(QPushButton):
    def __init__(self, text: str):
        super().__init__(text)
        self.setFixedWidth(50)


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
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.grid_layout)

        self.clmn += 1
        self.back_btn = HistoryBtn(BACK_SYM)
        self.back_btn.clicked.connect(lambda: self.navigate(-1))
        self.grid_layout.addWidget(self.back_btn, 0, self.clmn)

        self.clmn += 1
        self.next_btn = HistoryBtn(NEXT_SYM)
        self.next_btn.clicked.connect(lambda: self.navigate(1))
        self.grid_layout.addWidget(self.next_btn, 0, self.clmn)

        self.clmn += 1
        self.level_up_btn = QPushButton(UP_CURVE)
        self.level_up_btn.setFixedWidth(50)
        self.level_up_btn.clicked.connect(self.level_up)
        self.grid_layout.addWidget(self.level_up_btn, 0, self.clmn)

        self.clmn += 1
        self.grid_layout.setColumnStretch(self.clmn, 10)
        self.grid_layout.addItem(QSpacerItem(1, 1), 0, self.clmn)

        self.clmn += 1
        self.view_type_btn = ViewTypeBtn()
        self.grid_layout.addWidget(self.view_type_btn, 0, self.clmn)

        self.clmn += 1
        self.sort_type_btn = SortTypeBtn(parent=self)
        self.grid_layout.addWidget(self.sort_type_btn, 0, self.clmn)

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

        SignalsApp.all.new_history.connect(self.new_history)
        SignalsApp.all.new_history.emit(JsonData.root)
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
            SignalsApp.all.load_standart_grid.emit(self.history[self.index_])
        except (ValueError, IndexError):
            pass

    def level_up(self, e):
        root = os.path.dirname(JsonData.root)
        if not root == os.sep:
            SignalsApp.all.new_history.emit(root)
            SignalsApp.all.load_standart_grid.emit(root)