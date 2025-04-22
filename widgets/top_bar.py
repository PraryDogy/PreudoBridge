import os

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QAction, QCheckBox, QGroupBox, QHBoxLayout,
                             QLabel, QPushButton, QVBoxLayout, QWidget)

from cfg import Dynamic, Static

from ._base_items import (MinMaxDisabledWin, SearchItem, UFrame, ULineEdit,
                          UMenu, UTextEdit)
from .settings_win import SettingsWin

SEARCH_PLACE = "Место поиска:"
LIST_FILES = "Список файлов (по одному в строке):"
SEARCH_LIST_TEXT = "Найти по списку"
SEARCH_EXTENSIONS = {
    "Найти jpg": (".jpg", ".jpeg", "jfif"),
    "Найти png": (".png"),
    "Найти tiff": (".tif", ".tiff"),
    "Найти psd/psb": (".psd", ".psb"),
    "Найти raw": (".nef", ".raw"),
    "Найти любые фото": Static.IMG_EXT
}

class ActionData:
    __slots__ = ["sort", "reversed", "text"]

    def __init__(self, sort: str | None, reversed: bool, text: str):
        self.sort: str | None = sort
        self.reversed: bool = reversed
        self.text: str = text


class BarTopBtn(UFrame):
    clicked = pyqtSignal()

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

    def mouseReleaseEvent(self, a0):
        self.clicked.emit()
        return super().mouseReleaseEvent(a0)


class ListWin(MinMaxDisabledWin):
    ok_pressed = pyqtSignal()

    def __init__(self, search_item: SearchItem):
        super().__init__()
        self.search_item = search_item

        self.setFixedSize(570, 500)
        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 5, 10, 5)
        v_lay.setSpacing(10)
        self.setLayout(v_lay)

        first_row = QGroupBox()
        v_lay.addWidget(first_row)
        first_lay = QVBoxLayout()
        first_row.setLayout(first_lay)
        first_title = QLabel(text=SEARCH_PLACE)
        first_lay.addWidget(first_title)
        self.main_dir_label = QLabel()
        first_lay.addWidget(self.main_dir_label)

        inp_label = QLabel(LIST_FILES)
        v_lay.addWidget(inp_label)

        self.input_ = UTextEdit()
        v_lay.addWidget(self.input_)

        btns_wid = QWidget()
        v_lay.addWidget(btns_wid)
        btns_lay = QHBoxLayout()
        btns_lay.setContentsMargins(0, 0, 0, 0)
        btns_wid.setLayout(btns_lay)

        btns_lay.addStretch()

        ok_btn = QPushButton(text="Ок")
        ok_btn.clicked.connect(self.ok_cmd)
        ok_btn.setFixedWidth(100)
        btns_lay.addWidget(ok_btn)

        can_btn = QPushButton(text="Отмена")
        can_btn.clicked.connect(self.close)
        can_btn.setFixedWidth(100)
        btns_lay.addWidget(can_btn)

        btns_lay.addStretch()

    def ok_cmd(self, *args):
        search_list = self.input_.toPlainText()
        search_list = [
            i.strip()
            for i in search_list.split("\n")
            if i
        ]

        self.search_item.search_list.clear()

        for i in search_list:
            filename, ext = os.path.splitext(i)
            self.search_item.search_list.append(filename)

        self.ok_pressed.emit()
        self.close()

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.close()

 
class SearchWidget(QWidget):
    search_was_cleaned = pyqtSignal()
    start_search = pyqtSignal()
    list_win_opened = pyqtSignal()

    def __init__(self, search_item: SearchItem):
        super().__init__()
        self.search_item = search_item

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
        self.search_timer.timeout.connect(lambda: self.search_timer_cmd())

        self.templates_menu = UMenu(parent=self)

        for text, _ in SEARCH_EXTENSIONS.items():
            action = QAction(text, self)

            action.triggered.connect(
                lambda e, xx=text: self.action_cmd(xx)
            )

            self.templates_menu.addAction(action)

        search_list = QAction(SEARCH_LIST_TEXT, self)
        search_list.triggered.connect(self.search_list_cmd)
        self.templates_menu.addAction(search_list)

    def search_timer_cmd(self):
        self.start_search.emit()

    def clear_without_signal(self):
        # отключаем сигналы, чтобы при очистке виджета не запустился
        # on_text_changed и поиск пустышки
        self.search_wid.disconnect()
        self.search_wid.clear()
        self.search_wid.clear_btn.hide()
        # подключаем назад
        self.search_wid.textChanged.connect(self.on_text_changed)

    def on_text_changed(self, text: str):
        self.search_timer.stop()
        if text:
            self.search_wid.clear_btn.show()
            self.search_text = text.strip()
            self.search_wid.setText(self.search_text)
            self.search_item.reset()

            if text in SEARCH_EXTENSIONS:
                self.search_item.set_search_extenstions(SEARCH_EXTENSIONS.get(text))
            else:
                self.search_item.set_search_text(self.search_text)

            self.search_timer.start(1500)
        else:
            self.clear_without_signal()
            self.search_wid.clear_btn.hide()
            self.search_was_cleaned.emit()
            self.search_item.reset()

    def show_templates(self, a0: QMouseEvent | None) -> None:
        self.templates_menu.exec(self.mapToGlobal(self.rect().bottomLeft()))
    
    def action_cmd(self, text: str):
        self.search_wid.setText(text)

    def search_list_cmd(self):
        self.list_win = ListWin()
        self.list_win.ok_pressed.connect(self.list_win_cmd)
        self.list_win_opened.emit()
        self.list_win.center(self.window())
        self.list_win.show()

    def list_win_cmd(self, *args):
        self.search_wid.setText(SEARCH_LIST_TEXT)


class TopBar(QWidget):
    level_up = pyqtSignal()
    change_view = pyqtSignal(int)
    start_search = pyqtSignal()
    search_was_cleaned = pyqtSignal()
    navigate = pyqtSignal(str)
    list_win_opened = pyqtSignal()
    clear_data_clicked = pyqtSignal()
    open_in_new_win = pyqtSignal(str)

    def __init__(self, search_item: SearchItem):
        super().__init__()
        self.search_item = search_item
        self.setFixedHeight(40)

        self.history: list[str] = []
        self.index_: int = 0

        self.main_lay = QHBoxLayout()
        self.main_lay.setSpacing(0)
        self.main_lay.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_lay)

        back = BarTopBtn()
        back.load(Static.NAVIGATE_BACK_SVG)
        back.clicked.connect(lambda: self.navigate_cmd(offset=-1))
        self.main_lay.addWidget(back)

        next = BarTopBtn()
        next.load(Static.NAVIGATE_NEXT_SVG)
        next.clicked.connect(lambda: self.navigate_cmd(offset=1))
        self.main_lay.addWidget(next)

        level_up_btn = BarTopBtn()
        level_up_btn.clicked.connect(self.level_up.emit)
        level_up_btn.load(Static.FOLDER_UP_SVG)
        self.main_lay.addWidget(level_up_btn)

        self.main_lay.addStretch(1)

        self.new_win_btn = BarTopBtn()
        self.new_win_btn.mouseReleaseEvent = lambda e: self.open_in_new_win.emit("")
        self.new_win_btn.load(Static.NEW_WIN_SVG)
        self.main_lay.addWidget(self.new_win_btn)

        grid_view_btn = BarTopBtn()
        grid_view_btn.clicked.connect(lambda: self.change_view.emit(0))
        grid_view_btn.load(Static.GRID_VIEW_SVG)
        self.main_lay.addWidget(grid_view_btn)
    
        list_view_btn = BarTopBtn()
        list_view_btn.clicked.connect(lambda: self.change_view.emit(1))
        list_view_btn.load(Static.LIST_VIEW_SVG)
        self.main_lay.addWidget(list_view_btn)

        self.sett_btn = BarTopBtn()
        self.sett_btn.mouseReleaseEvent = self.open_settings_win
        self.sett_btn.load(Static.SETTINGS_SVG)
        self.main_lay.addWidget(self.sett_btn)

        self.main_lay.addStretch(1)

        self.search_wid = SearchWidget(self.search_item)
        self.search_wid.start_search.connect(self.start_search.emit)
        self.search_wid.search_was_cleaned.connect(self.search_was_cleaned.emit)
        self.search_wid.list_win_opened.connect(self.list_win_opened.emit)
        self.main_lay.addWidget(self.search_wid)

        self.index_ -= 1

    def set_main_dir(self, main_dir: str):
        try:
            self.search_wid.list_win.main_dir_label.setText(main_dir)
        except RuntimeError as e:
            print("bar top > set list win title", e)

    def open_settings_win(self, *args):
        self.sett_win = SettingsWin()
        self.sett_win.clear_data_clicked.connect(self.clear_data_clicked.emit)
        self.sett_win.center(self.window())
        self.sett_win.show()

    def new_history_item_cmd(self, dir: str):
        if dir == os.sep:
            return

        if len(self.history) > 100:
            self.history.pop(-1)

        self.history.append(dir)
        self.index_ = len(self.history) - 1

    def navigate_cmd(self, offset: int):
        try:
            if self.index_ + offset in(-1, len(self.history)):
                return
            self.index_ += offset
            new_main_dir = self.history[self.index_]
            self.navigate.emit(new_main_dir)
        except (ValueError, IndexError) as e:
            print("bar top > navigate cmd > error", e)
