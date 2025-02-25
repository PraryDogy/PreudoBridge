from PyQt5.QtCore import QSize, Qt
from PyQt5.QtWidgets import QAction, QListWidget, QListWidgetItem, QMenu

from cfg import Dynamic, Static
from signals import SignalsApp

from ._base import UMenu


class UItem(QListWidgetItem):
    def __init__(self):
        super().__init__()
        self.rating: int


class TreeTags(QListWidget):
    def __init__(self):
        super().__init__()

        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.setFixedHeight(230)
        item_size = QSize(self.width(), 25)

        # копия механик из _actions.py > TagsMenu

        # NO_TAGS_T_ = Static.LINE_SYM + " " + Static.NO_TAGS_T
        DEINED_T_ = Static.DEINED_SYM + " " + Static.DEINED_T
        REVIEW_T_ = Static.REVIEW_SYM  + " " + Static.REVIEW_T
        APPROVED_T_ = Static.APPROVED_SYM  + " " + Static.APPROVED_T

        actions = {
            # NO_TAGS_T_: 9,
            DEINED_T_: 6,
            REVIEW_T_: 7,
            APPROVED_T_: 8
        }
        # конец копии

        zero_item = UItem()
        zero_item.rating = 0
        zero_item.setText(Static.LINE_SYM)
        zero_item.setSizeHint(item_size)
        self.addItem(zero_item)

        for i in range(1, 6):
            item = UItem()
            item.rating = i
            item.setText(Static.STAR_SYM * i)
            item.setSizeHint(item_size)
            self.addItem(item)

        for text, int_ in actions.items():
            item = UItem()
            item.rating = int_
            item.setText(text)
            item.setSizeHint(item_size)
            self.addItem(item)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.itemClicked.connect(self.handle_item_click)

    def show_context_menu(self, position):

        item: UItem = self.itemAt(position)

        if not item:
            return

        menu = UMenu()

        enable_action = QAction(text="Включить")

        if Dynamic.rating_filter == item.rating:
            enable_action.setDisabled(True)

        enable_action.triggered.connect(
            lambda: self.item_cmd(rating=item.rating)
        )

        menu.addAction(enable_action)
        menu.show_custom()

    def handle_item_click(self, item: UItem):

        if item.rating > 5:
            value = item.rating % 10
        else:
            value = item.rating

        self.item_cmd(
            rating=value
        )

    def item_cmd(self, rating: int):
        Dynamic.rating_filter = rating
        SignalsApp.instance.filter_grid.emit()

    def reset(self):
        Dynamic.rating_filter = 0
        self.setCurrentRow(0)