import os

from PyQt5.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QAction, QHBoxLayout, QLabel, QTabBar,
                             QVBoxLayout, QWidget)

from cfg import Dynamic, JsonData, Static
from signals import SignalsApp
from utils import Utils

from ._base import UFrame, ULineEdit, UMenu
from .win_settings import WinSettings


class ActionData:
    __slots__ = ["sort", "reversed", "text"]

    def __init__(self, sort: str | None, reversed: bool, text: str):
        self.sort: str | None = sort
        self.reversed: bool = reversed
        self.text: str = text


class BarTopBtn(UFrame):
    def __init__(self):
        super().__init__()
        self.setFixedSize(45, 35)

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        self.setLayout(h_lay)

        self.svg_btn = QSvgWidget()
        self.svg_btn.setFixedSize(17, 17)
        h_lay.addWidget(self.svg_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def load(self, path: str):
        self.svg_btn.load(path)

 
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
            lambda: SignalsApp.instance.load_search_grid.emit(self.search_text)
            )
        
        self.clear_search.connect(self.costil)

        self.templates_menu = UMenu()

        for text, template in Static.SEARCH_TEMPLATES.items():
            action = QAction(parent=self, text=text)

            action.triggered.connect(
                lambda e, xx=text: self.action_cmd(xx)
            )

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
            SignalsApp.instance.load_standart_grid_cmd(
                path=JsonData.root,
                prev_path=None
            )

    def show_templates(self, a0: QMouseEvent | None) -> None:
        self.templates_menu.exec(self.mapToGlobal(self.rect().bottomLeft()))
    
    def action_cmd(self, text: str):
        self.search_wid.setText(text)


class FiltersBtn(BarTopBtn):
    def __init__(self):
        super().__init__()
        self.load(Static.RATING_SVG)
        
        self.menu_ = QWidget()
        self.menu_.setWindowFlags(Qt.WindowType.Popup)

        self.menu_.setLayout(QVBoxLayout())
        self.menu_.layout().setContentsMargins(0, 0, 0, 0)
        self.menu_.layout().setSpacing(1)

        # строчка с цветами

        rating_wid = QWidget()
        self.menu_.layout().addWidget(rating_wid)
        rating_lay = QHBoxLayout()
        rating_lay.setContentsMargins(3, 3, 3, 3)
        rating_lay.setSpacing(5)
        rating_wid.setLayout(rating_lay)

        self.rating_data = {
            i: False
            for i in range(1, 6)
        }

        self.rating_wids: list[QLabel] = []

        reset_rating = QLabel(Static.LINE_SYM)
        reset_rating.setAlignment(Qt.AlignmentFlag.AlignCenter)
        reset_rating.setFixedSize(20, 20)
        reset_rating.mouseReleaseEvent = lambda e: self.reset_filters()
        rating_lay.addWidget(reset_rating)

        for rate in self.rating_data:
            label = QLabel(Static.STAR_SYM)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedSize(20, 20)
            label.mouseReleaseEvent = lambda e, r=rate: self.toggle_rating(r)
            rating_lay.addWidget(label)
            self.rating_wids.append(label)
        
        self.menu_.adjustSize()

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            pont = self.rect().bottomLeft()
            self.menu_.move(self.mapToGlobal(pont))
            self.menu_.show()

    def toggle_rating(self, rate: int):
        Dynamic.rating_filter = rate

        for i in self.rating_wids[:rate]:

            i.setStyleSheet(
                f"""
                    background: {Static.BLUE};
                    border-radius: 3px;
                """
            )

        for i in self.rating_wids[rate:]:
            i.setStyleSheet("")

        SignalsApp.instance.filter_grid.emit()

    def reset_filters(self):

        Dynamic.rating_filter = 0

        for i in self.rating_wids:
            i.setStyleSheet("")

        SignalsApp.instance.filter_grid.emit()


class BarTop(QWidget):

    def __init__(self):
        super().__init__()
        self.setFixedHeight(40)
        self.clmn = 0

        self.root: str = None
        self.history: list[str] = []
        self.index_: int = 0

        self.main_lay = QHBoxLayout()
        self.main_lay.setSpacing(0)
        self.main_lay.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_lay)

        back = BarTopBtn()
        back.load(Static.NAVIGATE_BACK_SVG)
        back.mouseReleaseEvent = lambda e: self.navigate(offset=-1)
        self.main_lay.addWidget(back)

        next = BarTopBtn()
        next.load(Static.NAVIGATE_NEXT_SVG)
        next.mouseReleaseEvent = lambda e: self.navigate(offset=1)
        self.main_lay.addWidget(next)

        self.folder_up_btn = BarTopBtn()
        self.folder_up_btn.mouseReleaseEvent = self.folder_up_cmd
        self.folder_up_btn.load(Static.FOLDER_UP_SVG)
        self.main_lay.addWidget(self.folder_up_btn)

        self.main_lay.addStretch(1)

        self.grid_view = BarTopBtn()
        self.grid_view.mouseReleaseEvent = lambda e: self.change_view_cmd(index=0)
        self.grid_view.load(Static.GRID_VIEW_SVG)
        self.main_lay.addWidget(self.grid_view)
    
        self.list_view = BarTopBtn()
        self.list_view.mouseReleaseEvent = lambda e: self.change_view_cmd(index=1)
        self.list_view.load(Static.LIST_VIEW_SVG)
        self.main_lay.addWidget(self.list_view)

        self.filters_btn = FiltersBtn()
        self.main_lay.addWidget(self.filters_btn)

        self.sett_btn = BarTopBtn()
        self.sett_btn.mouseReleaseEvent = self.open_settings_win
        self.sett_btn.load(Static.SETTINGS_SVG)
        self.main_lay.addWidget(self.sett_btn)

        self.main_lay.addStretch(1)

        self.search_wid = SearchWidget()
        self.main_lay.addWidget(self.search_wid)

        SignalsApp.instance.new_history_item.connect(self.new_history)
        SignalsApp.instance.new_history_item.emit(JsonData.root)
        self.index_ -= 1

    def change_view_cmd(self, index: int, *args):
        Dynamic.grid_view_type = index
        SignalsApp.instance.load_standart_grid_cmd(
            path=JsonData.root,
            prev_path=None
        )

    def open_settings_win(self, *args):
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
            SignalsApp.instance.load_standart_grid_cmd(
                path=self.history[self.index_],
                prev_path=None
            )
        except (ValueError, IndexError):
            pass

    def folder_up_cmd(self, *args):

        old_root = JsonData.root
        root = os.path.dirname(JsonData.root)

        if not root == os.sep:

            SignalsApp.instance.new_history_item.emit(root)

            SignalsApp.instance.load_standart_grid_cmd(
                path=root,
                prev_path=old_root
            )