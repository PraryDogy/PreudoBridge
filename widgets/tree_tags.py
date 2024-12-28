from PyQt5.QtWidgets import QListWidget, QMenu, QListWidgetItem, QAction
from PyQt5.QtCore import Qt, QSize
from cfg import Static
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

        self.setFixedHeight(170)
        item_size = QSize(self.width(), 25)

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

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.itemClicked.connect(self.handle_item_click)

    def show_context_menu(self, position):

        item: UItem = self.itemAt(position)

        if not item:
            return

        menu = UMenu()
        enable_action = QAction(text="Включить")

        enable_action.triggered.connect(
            lambda: self.item_cmd(rating=item.rating)
        )

        menu.addAction(enable_action)
        menu.show_custom()

    def handle_item_click(self, item: UItem):
        self.item_cmd(
            rating=item.rating
        )

    def item_cmd(self, rating: int):
        print(rating)

