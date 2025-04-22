from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QVBoxLayout,
                             QWidget)

from cfg import Dynamic


class SearchBar(QFrame):
    start_new_search = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFixedHeight(40)

        self.exactly_search = False

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)
        self.setLayout(h_lay)

        self.checkbox = QCheckBox(" Точное соответствие")
        self.checkbox.stateChanged.connect(self.on_state_change)
        h_lay.addWidget(self.checkbox)

    def on_state_change(self, value: int):
        data = {0: False, 2: True}
        self.exactly_search = data.get(value)
        self.start_new_search.emit()

    def get_exactly_search(self):
        return self.exactly_search

    def show(self):
        self.checkbox.setChecked(self.exactly_search)
        return super().show()