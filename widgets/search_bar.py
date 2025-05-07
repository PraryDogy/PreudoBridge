from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel,
                             QPushButton, QVBoxLayout, QWidget)

from utils import Utils

from ._base_items import SearchItem, UFrame


class SpinnerWidget(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.spinner_symbols = ["◯", "◌", "●"]
        self.current_symbol_index = 0

        # Устанавливаем начальный текст и стиль
        self.setAlignment(Qt.AlignCenter)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_spinner)
        self.timer.start(200)  # Обновление каждую 200 миллисекунд

    def update_spinner(self):
        self.setText(self.spinner_symbols[self.current_symbol_index])
        self.current_symbol_index = (self.current_symbol_index + 1) % len(self.spinner_symbols)


class SearchBar(QFrame):
    load_search_grid = pyqtSignal()
    pause_search_sig = pyqtSignal(bool)
    on_text_click = pyqtSignal()
    on_extensions_click = pyqtSignal()
    on_list_click = pyqtSignal()

    def __init__(self, search_item: SearchItem):
        super().__init__()
        self.setFixedHeight(40)
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

        self.checkbox = QCheckBox(" Точное соответствие")
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
            self.pause_btn.setText("Пауза")
        else:
            self.pause_flag = True
            self.pause_btn.setText("Продолжить")

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
        self.load_search_grid.emit()

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
        if len(text) > 30:
            text = text[:30] + "..."
        self.descr_lbl.setText(text)
        self.pause_btn.setDisabled(False)
        self.pause_btn.setText("Пауза")
        self.pause_flag = False

        return super().show()

    def search_bar_search_fin(self):
        self.descr_lbl.setText("Поиск завершен")
        self.pause_btn.setDisabled(True)

    def on_frame_click(self, e):
        if self.search_item.get_files_list():
            self.on_list_click.emit()
        elif self.search_item.get_extensions():
            self.on_extensions_click.emit()
        else:
            self.on_text_click.emit()