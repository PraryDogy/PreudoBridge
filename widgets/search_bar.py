from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton

from utils import Utils

from ._base_items import SearchItem, UFrame


class SearchBar(QFrame):
    exactly_clicked = pyqtSignal()
    pause_search_sig = pyqtSignal(bool)
    on_text_click = pyqtSignal()
    on_exts_click = pyqtSignal()
    on_list_click = pyqtSignal()
    heigt_ = 40
    checkbox_text = " Точное соответствие"
    pause_text = "Пауза"
    continue_text = "Продолжить"
    searching_text = "Идет поиск"
    search_finished_text = "Поиск завершен"
    text_limit = 30

    def __init__(self, search_item: SearchItem):
        super().__init__()
        self.setFixedHeight(SearchBar.heigt_)
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

        self.checkbox = QCheckBox(SearchBar.checkbox_text)
        self.checkbox.stateChanged.connect(self.on_state_change)
        h_lay.addWidget(self.checkbox)

        self.pause_btn = QPushButton()
        self.pause_btn.setFixedWidth(110)
        self.pause_btn.clicked.connect(self.pause_btn_cmd)
        h_lay.addWidget(self.pause_btn)

        h_lay.addStretch()

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

    def on_state_change(self, value: int):
        """
        Обрабатывает изменение состояния чекбокса (сигнал stateChanged):

        - Если активен stop_flag — выход без действий.
        - Преобразует значение состояния чекбокса (0 = unchecked, 2 = checked)
        в булев тип и сохраняет в SearchItem.exactly.
        - Испускает сигнал load_search_grid для загрузки сетки GridSearch
        с новым параметром SearchItem.exaclty
        """
        if self.stop_flag:
            return
        data = {0: False, 2: True}
        new_value = data.get(value)
        self.search_item.exactly = new_value
        self.exactly_clicked.emit()

    def show(self):
        """
        Отображает панель поиска (SearchBar):

        - Включает стоп-флаг, чтобы предотвратить реакцию на изменение состояния чекбокса.
        - Устанавливает состояние чекбокса в соответствии с текущим значением search_item.exactly.
        - Отключает чекбокс, если установлен поиск по расширениям (в этом случае точность неактуальна).
        - Отключает стоп-флаг и отображает SearchBar.
        """
        self.stop_flag = True
        self.checkbox.setChecked(self.search_item.exactly)
        self.stop_flag = False

        if self.search_item.get_extensions():
            self.checkbox.setDisabled(True)
        else:
            self.checkbox.setDisabled(False)

        text = self.search_item.get_text()
        if len(text) > SearchBar.text_limit:
            text = text[:SearchBar.text_limit] + "..."
        text = f"{SearchBar.searching_text}: \"{text}\""

        self.descr_lbl.setText(text)
        self.pause_btn.setDisabled(False)
        self.pause_btn.setText(SearchBar.pause_text)
        self.pause_flag = False

        return super().show()

    def search_bar_search_fin(self):
        self.descr_lbl.setText(SearchBar.search_finished_text)
        self.pause_btn.setDisabled(True)

    def on_frame_click(self, e):
        if self.search_item.get_files_list():
            self.on_list_click.emit()
        elif self.search_item.get_extensions():
            self.on_exts_click.emit()
        else:
            self.on_text_click.emit()