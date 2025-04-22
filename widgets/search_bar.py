from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QVBoxLayout,
                             QWidget)

from cfg import Dynamic

from ._base_items import SearchItem


class SearchBar(QFrame):
    toggle_exactly = pyqtSignal()

    def __init__(self, search_item: SearchItem):
        super().__init__()
        self.setFixedHeight(40)
        self.search_item = search_item

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)
        self.setLayout(h_lay)

        self.checkbox = QCheckBox(" Точное соответствие")
        self.checkbox.stateChanged.connect(self.on_state_change)
        h_lay.addWidget(self.checkbox)

    def on_state_change(self, value: int):
        data = {0: False, 2: True}
        new_value = data.get(value)
        self.search_item.exactly = new_value
        self.toggle_exactly.emit()

    def show(self):
        self.checkbox.setChecked(self.search_item.exactly)
        return super().show()