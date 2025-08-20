from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import (QAction, QFrame, QHBoxLayout, QLabel, QMenu,
                             QPushButton)

from system.items import SearchItem
from system.utils import Utils

from ._base_widgets import UFrame


class BlinkingLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._timer = QTimer(self)
        self._timer.setInterval(500)  # 1 секунда
        self._timer.timeout.connect(self._toggle_color)
        self._blink_color = QColor(128, 128, 128) 
        self._is_blink_on = False

    def _toggle_color(self):
        if self._is_blink_on:
            self.setStyleSheet("")
        else:
            self.setStyleSheet(f"color: {self._blink_color.name()};")
        self._is_blink_on = not self._is_blink_on

    def start_blink(self):
        self._default_color = self.palette().color(QPalette.WindowText)
        self._timer.start()

    def stop_blink(self):
        self._timer.stop()
        self.setStyleSheet("")
        self._is_blink_on = False


class SearchBar(QFrame):
    on_filter_clicked = pyqtSignal()
    on_pause_clicked = pyqtSignal(bool)
    on_search_bar_clicked = pyqtSignal()

    height_ = 40
    pause_text = "Пауза"
    continue_text = "Продолжить"
    searching_text = "Идет поиск"
    search_finished_text = "Поиск завершен"
    text_limit = 30
    # чтобы на всех темах текст был одинаково по левому краю и с отступом
    # по другому универсально не выходит
    no_filter_text = "  Найти похожие"
    exactly_text = "  Точное соответствие"
    containts_text = "  Содержится в имени"

    def __init__(self, search_item: SearchItem):
        super().__init__()
        self.setFixedHeight(SearchBar.height_)
        self.search_item: SearchItem = search_item
        self.stop_flag: bool = False
        self.pause_flag: bool = False

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)
        self.setLayout(h_lay)

        uframe = UFrame()
        h_lay.addWidget(uframe)
        uframe_lay = QHBoxLayout()
        uframe_lay.setContentsMargins(0, 0, 0, 0)
        uframe.setLayout(uframe_lay)
        uframe.mouseReleaseEvent = lambda e: self.on_search_bar_clicked.emit()

        self.descr_lbl = BlinkingLabel(self.searching_text)
        uframe_lay.addWidget(self.descr_lbl)

        self.filter_bt = QPushButton()
        self.filter_bt.setStyleSheet("text-align: left;")
        self.filter_bt.setFixedWidth(190)
        h_lay.addWidget(self.filter_bt)

        menu = QMenu()
        menu.setFixedWidth(190)
        self.filter_bt.setMenu(menu)

        for i in (self.no_filter_text, self.exactly_text, self.containts_text):
            act = QAction(i, menu)
            act.triggered.connect(lambda e, act=act: self.menu_clicked(act))
            menu.addAction(act)

        self.pause_btn = QPushButton()
        self.pause_btn.setFixedWidth(110)
        self.pause_btn.clicked.connect(self.pause_btn_cmd)
        h_lay.addWidget(self.pause_btn)

        h_lay.addStretch()

    def menu_clicked(self, act: QAction):
        self.filter_bt.setText(act.text())

        data = {
            self.no_filter_text: 0,
            self.exactly_text: 1,
            self.containts_text: 2
        }
        
        self.search_item.set_filter(data.get(act.text()))
        self.on_filter_clicked.emit()

    def pause_btn_cmd(self):
        if self.pause_flag:
            self.pause_flag = False
            self.pause_btn.setText(SearchBar.pause_text)
        else:
            self.pause_flag = True
            self.pause_btn.setText(SearchBar.continue_text)
        self.on_pause_clicked.emit(self.pause_flag)

    def show(self):
        """
        Отображает панель поиска (SearchBar):

        - Включает стоп-флаг, чтобы предотвратить реакцию на изменение состояния чекбокса.
        - Устанавливает состояние чекбокса в соответствии с текущим значением search_item.exactly.
        - Отключает чекбокс, если установлен поиск по расширениям (в этом случае точность неактуальна).
        - Отключает стоп-флаг и отображает SearchBar.
        """
        data = {
            0: self.no_filter_text,
            1: self.exactly_text,
            2: self.containts_text
        }

        filter_value = self.search_item.get_filter()
        self.filter_bt.setText(data.get(filter_value, self.no_filter_text))

        if isinstance(self.search_item.get_content(), tuple):
            self.filter_bt.setDisabled(True)
            self.filter_bt.hide()
        else:
            self.filter_bt.setDisabled(False)
            self.filter_bt.show()

        self.pause_btn.setDisabled(False)
        self.pause_btn.setText(SearchBar.pause_text)
        self.pause_flag = False
        self.descr_lbl.setText(self.searching_text)
        self.descr_lbl.start_blink()

        return super().show()
    
    def hide(self):
        self.search_bar_search_fin()
        return super().hide()

    def search_bar_search_fin(self):
        self.descr_lbl.setText(self.search_finished_text)
        self.descr_lbl.stop_blink()
        self.pause_btn.setDisabled(True)