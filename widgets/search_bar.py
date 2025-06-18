from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (QAction, QCheckBox, QFrame, QHBoxLayout, QLabel,
                             QMenu, QPushButton)

from utils import Utils

from ._base_items import SearchItem, UFrame


class SearchBar(QFrame):
    on_filter_clicked = pyqtSignal()
    pause_search_sig = pyqtSignal(bool)
    on_text_click = pyqtSignal()
    on_exts_click = pyqtSignal()
    on_list_click = pyqtSignal()
    height_ = 40
    pause_text = "Пауза"
    continue_text = "Продолжить"
    searching_text = "Идет поиск"
    search_finished_text = "Поиск завершен"
    text_limit = 30
    no_filter_text = "Без фильтра"
    exactly_text = "Точное соответствие"
    containts_text = "Содержится в имени"

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
        uframe.mouseReleaseEvent = self.on_frame_click

        self.descr_lbl = QLabel()
        uframe_lay.addWidget(self.descr_lbl)

        self.menu_btn = QPushButton(self.no_filter_text)
        self.menu_btn.setFixedWidth(180)
        h_lay.addWidget(self.menu_btn)

        menu = QMenu()
        self.menu_btn.setMenu(menu)

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
        self.menu_btn.setText(act.text())

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

        try:
            self.pause_search_sig.emit(self.pause_flag)
        except RuntimeError as e:
            Utils.print_error(e)

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
        self.menu_btn.setText(data.get(filter_value))

        if isinstance(self.search_item.get_content(), tuple):
            self.menu_btn.setDisabled(True)
        else:
            self.menu_btn.setDisabled(False)

        self.pause_btn.setDisabled(False)
        self.pause_btn.setText(SearchBar.pause_text)
        self.pause_flag = False

        return super().show()

    def search_bar_search_fin(self):
        self.descr_lbl.setText(SearchBar.search_finished_text)
        self.pause_btn.setDisabled(True)

    def on_frame_click(self, e):
        if isinstance(self.search_item.get_content(), list):
            self.on_list_click.emit()
        elif isinstance(self.search_item.get_content(), tuple):
            self.on_exts_click.emit()
        else:
            self.on_text_click.emit()