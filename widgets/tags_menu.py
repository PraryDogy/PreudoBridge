from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import QAction, QListWidget, QListWidgetItem, QMenu

from cfg import Dynamic, Static

from ._base_widgets import UMenu

ENABLE_T = "Включить"


class UItem(QListWidgetItem):
    def __init__(self):
        super().__init__()
        self.rating: int


class TagsMenu(QListWidget):
    filter_grid_sig = pyqtSignal()
    rearrange_grid_sig = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.setFixedHeight(230)
        item_size = QSize(self.width(), 25)

        # копия механик из _actions.py > TagsMenu

        # NO_TAGS_T_ = Static.LINE_SYM + " " + Static.NO_TAGS_T
        DEINED_T_ = Static.DEINED_SYM + " " + Static.TAGS_DEINED
        REVIEW_T_ = Static.REVIEW_SYM  + " " + Static.TAGS_REVIEW
        APPROVED_T_ = Static.APPROVED_SYM  + " " + Static.TAGS_APPROWED

        actions = {
            # NO_TAGS_T_: 9,
            DEINED_T_: 6,
            REVIEW_T_: 7,
            APPROVED_T_: 8
        }
        # конец копии

        zero_item = UItem()
        zero_item.rating = 0
        zero_item.setText(Static.LINE_LONG_SYM)
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

        enable_action = QAction(ENABLE_T, menu)

        if Dynamic.rating_filter == item.rating:
            enable_action.setDisabled(True)

        enable_action.triggered.connect(
            lambda: self.item_cmd(rating=item.rating)
        )

        menu.addAction(enable_action)
        menu.show_()

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
        self.filter_grid_sig.emit()
        self.rearrange_grid_sig.emit()

    def reset(self):
        Dynamic.rating_filter = 0
        self.setCurrentRow(0)