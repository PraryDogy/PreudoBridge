from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel,
                             QVBoxLayout, QWidget)


from ._base_items import SearchItem


class SpinnerWidget(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.spinner_symbols = ["◯", "◌", "⬤", "●"]
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

    def __init__(self, search_item: SearchItem):
        super().__init__()
        self.setFixedHeight(40)
        self.search_item: SearchItem = search_item
        self.stop_flag: bool = False

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)
        self.setLayout(h_lay)

        self.checkbox = QCheckBox(" Точное соответствие")
        self.checkbox.stateChanged.connect(self.on_state_change)
        h_lay.addWidget(self.checkbox)

        h_lay.addStretch()

        self.descr_lbl = QLabel("Идет поиск")
        h_lay.addWidget(self.descr_lbl)

        self.spinner = SpinnerWidget()
        self.spinner.setFixedSize(20, 20)
        h_lay.addWidget(self.spinner)

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
        return super().show()
    
    def show_spinner(self):
        self.descr_lbl.show()
        self.spinner.show()

    def hide_spinner(self):
        self.descr_lbl.hide()
        self.spinner.hide()