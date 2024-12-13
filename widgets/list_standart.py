import os

import sqlalchemy
from numpy import ndarray
from PyQt5.QtCore import QObject, Qt, pyqtSignal, QSize
from PyQt5.QtGui import (QCloseEvent, QContextMenuEvent, QDragEnterEvent,
                         QDropEvent, QMouseEvent, QPixmap)
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                             QMenu, QWidget)
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import JsonData, Static, ThumbData
from database import CACHE, Dbase, OrderItem
from fit_img import FitImg
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from ._actions import CopyPath, FavRemove, Rename, RevealInFinder, View
from ._finder_items import FinderItems, ImageData, LoadingWid
from ._grid import Grid
from .win_rename import WinRename

MAX_QUERIES = 10
SVG_SIZE = 15
LIST_ITEM_H = 30

PATH_NOT_EXISTS = [
    f"{JsonData.root}",
    "Такой папки не существует",
    "Проверьте подключение к сетевому диску"
]
PATH_NOT_EXISTS = "\n".join(PATH_NOT_EXISTS)

NO_IMAGES = [
    f"{JsonData.root}",
    "Нет изображений"
]
NO_IMAGES = "\n".join(NO_IMAGES)


class ListItem(QWidget):
    def __init__(self, svg_path: str, order_item: OrderItem):
        super().__init__()

        self.h_lay = QHBoxLayout()
        self.h_lay.setContentsMargins(10, 0, 0, 0)
        self.h_lay.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.setLayout(self.h_lay)

        self.img_wid = QSvgWidget()
        self.img_wid.load(svg_path)
        self.img_wid.setFixedSize(SVG_SIZE, SVG_SIZE)
        self.h_lay.addWidget(self.img_wid)

        t = [
                os.path.basename(order_item.src),
                order_item.colors,
                Static.STAR_SYM * order_item.rating
        ]

        t = " ".join(t)

        self.text_wid = QLabel(text=t)
        self.h_lay.addWidget(self.text_wid)


class ListStandart(QListWidget):
    def __init__(self):
        super().__init__()

        self.order_items: list[OrderItem] = []

        self.offset = 0
        self.limit = 100

        self.loading_lbl = LoadingWid(parent=self)
        Utils.center_win(self, self.loading_lbl)
        self.show()

        self.finder_task = FinderItems()
        self.finder_task.signals_.finished_.connect(self.finder_task_fin)
        UThreadPool.start(self.finder_task)

        self.verticalScrollBar().valueChanged.connect(self.on_scroll)

    def on_scroll(self, value: int):

        if value == self.verticalScrollBar().maximum():

            if self.offset > self.total:
                return
            else:
                self.offset += self.limit
                self.create_sorted_grid()

    def finder_task_fin(self, order_items: list[OrderItem]):

        self.loading_lbl.hide()
        self.order_items = order_items
        self.total = len(order_items)

        SignalsApp.all_._path_labels_cmd.emit(
            {"src": JsonData.root, "total": self.total}
        )

        self.create_sorted_grid()

    def create_sorted_grid(self):

        sys_disk = os.path.join(os.sep, "Volumes", "Macintosh HD")
        cut = self.order_items[self.offset:self.offset + self.limit]

        for order_item in cut:
    
            if os.path.isdir(order_item.src):

                wid = ListItem(
                    svg_path=Static.FOLDER_SVG,
                    order_item=order_item
                    )

                if os.path.ismount(order_item.src) or order_item.src == sys_disk:
                    wid.img_wid.load(Static.HDD_SVG)

            else:

                wid = ListItem(
                    svg_path=Static.IMG_SVG,
                    order_item = order_item
                )

            list_item = QListWidgetItem()
            size = QSize(wid.sizeHint().width(), LIST_ITEM_H)
            list_item.setSizeHint(size)

            self.addItem(list_item)
            self.setItemWidget(list_item, wid)

        if not os.path.exists(JsonData.root):
            setattr(self, "no_images", PATH_NOT_EXISTS)

        elif not self.order_items:
            setattr(self, "no_images", NO_IMAGES)

        if hasattr(self, "no_images"):
            print("no images")

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self.loading_lbl.deleteLater()
        return super().closeEvent(a0)

    def resizeEvent(self, a0):
        Utils.center_win(self, self.loading_lbl)
        return super().resizeEvent(a0)
    
    def rearrange(self, *args, **kwargs):
        print("list standart rearrange")