import os

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QAction, QGroupBox, QHBoxLayout, QLabel,
                             QPushButton, QVBoxLayout, QWidget)

from cfg import Static

from ._base_items import (MinMaxDisabledWin, SearchItem, UFrame, ULineEdit,
                          UMenu, UTextEdit)
from .settings_win import SettingsWin


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
    SEARCH_PLACE = "Место поиска:"
    LIST_FILES = "Список файлов (по одному в строке):"
    finished_ = pyqtSignal(list)

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
        first_title = QLabel(ListWin.SEARCH_PLACE)
        first_lay.addWidget(first_title)
        self.main_dir_label = QLabel()
        first_lay.addWidget(self.main_dir_label)

        inp_label = QLabel(ListWin.LIST_FILES)
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

        new_search_list: list[str] = []

        for i in search_list:
            filename, ext = os.path.splitext(i)
            new_search_list.append(filename)

        self.finished_.emit(new_search_list)
        self.close()

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.close()

 
class SearchWidget(QWidget):
    search_was_cleaned = pyqtSignal()
    start_search = pyqtSignal()
    get_main_dir = pyqtSignal()

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

        self.input_timer = QTimer(self)
        self.input_timer.setSingleShot(True)
        self.input_timer.timeout.connect(self.prepare_text)

        self.templates_menu = UMenu(parent=self)

        for text, _ in SearchItem.SEARCH_EXTENSIONS.items():
            action = QAction(text, self)

            action.triggered.connect(
                lambda e, xx=text: self.search_wid.setText(xx)
            )

            self.templates_menu.addAction(action)

        search_list = QAction(SearchItem.SEARCH_LIST_TEXT, self)
        search_list.triggered.connect(self.open_search_list_win)
        self.templates_menu.addAction(search_list)

        self.search_list_local: list[str] = []

    def clear_without_signal(self):
        # отключаем сигналы, чтобы при очистке виджета не запустился
        # on_text_changed и поиск пустышки
        self.search_wid.disconnect()
        self.search_wid.clear()
        self.search_wid.clear_btn.hide()
        # подключаем назад
        self.search_wid.textChanged.connect(self.on_text_changed)

    def on_text_changed(self, text: str):
        if text:
            self.search_text = text
            self.input_timer.stop()
            self.input_timer.start(1500)
        else:
            self.clear_without_signal()
            self.search_wid.clear_btn.hide()
            self.search_was_cleaned.emit()
            self.search_item.reset()

    def prepare_text(self):
        """
        - Отображает кнопку "стереть"
        - Подготавливает текст для поиска
        - Сбрасывает SearchItem для новых данных
        - Устанавливает текст в поле ввода
        - Устанавливает соответствующие тексту параметры:
            - Если текст равен ключу из SearchItem.SEARCH_EXTENSIONS,   
            устанавливает значение в SearchItem.search_extensions
            - Если текст равен SearchItem.SEARCH_LIST, присваивает значение
            из окна ввода ListWin в SearchItem.search_list
            - В остальных случаях устанавливает текст в поле ввода и присваивает
            текст в SearchItem.search_text
        - Испускает сигнал start_search
        """
        self.search_wid.clear_btn.show()
        self.search_text = self.search_text.strip()
        self.search_wid.setText(self.search_text)
        self.search_item.reset()

        if self.search_text in SearchItem.SEARCH_EXTENSIONS:
            extensions = SearchItem.SEARCH_EXTENSIONS.get(self.search_text)
            self.search_item.set_search_extenstions(extensions)

        elif self.search_text == SearchItem.SEARCH_LIST_TEXT:
            self.search_item.set_search_list(self.search_list_local)

        else:
            self.search_item.set_search_text(self.search_text)

        self.start_search.emit()

    def show_templates(self, a0: QMouseEvent | None) -> None:
        """
        Смотри формирование меню в инициаторе   
        Открывает меню на основе SearchItem.SEARCH_EXTENSIONS   
        При клике на пункт меню устанавливает:  
        - в окно поиска текст ключа из SearchItem.SEARCH_EXTENSIONS
        - в SearchItem.search_extensions значение соответствующего ключа    
        """
        self.templates_menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def open_search_list_win(self):
        """
        - Открывает окно для ввода списка файлов / папок для поиска   
        - Испускает сигнал finished со списком файлов из окна ввода
        """
        self.list_win = ListWin(self.search_item)
        self.list_win.finished_.connect(lambda search_list: self.list_win_finished(search_list))
        self.get_main_dir.emit()
        self.list_win.center(self.window())
        self.list_win.show()

    def list_win_finished(self, search_list: list[str]):
        """
        - Устанавливает значение search_list_local
        - Устанавливает текст в поле ввода
        - Автоматически запускается onTextChanged > self.prepare_text
        """
        self.search_list_local = search_list
        self.search_wid.setText(SearchItem.SEARCH_LIST_TEXT)


class TopBar(QWidget):
    level_up = pyqtSignal()
    change_view = pyqtSignal(int)
    start_search = pyqtSignal()
    search_was_cleaned = pyqtSignal()
    navigate = pyqtSignal(str)
    get_main_dir = pyqtSignal()
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
        self.search_wid.get_main_dir.connect(self.get_main_dir.emit)
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
