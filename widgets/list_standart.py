import os

import sqlalchemy
from numpy import ndarray
from PyQt5.QtCore import QObject, Qt, pyqtSignal
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
from ._thumb import Thumb, ThumbFolder
from .win_rename import WinRename

MAX_QUERIES = 10

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
    def __init__(self, text: str, svg_path: str):
        super().__init__()

        self.h_lay = QHBoxLayout()
        self.setLayout(self.h_lay)

        self.svg_wid = QSvgWidget()
        self.svg_wid.load(svg_path)
        self.h_lay.addWidget(self.svg_wid)

        self.text_wid = QLabel(text=text)
        self.h_lay.addWidget(self.text_wid)


class GridStandart(QListWidget):
    def __init__(self, width: int):
        super().__init__(width)

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

        SignalsApp.all_.path_labels_cmd.emit(
            {"src": JsonData.root, "total": self.total}
        )

        self.create_sorted_grid()

    def create_sorted_grid(self):

        sys_disk = os.path.join(os.sep, "Volumes", "Macintosh HD")
        col_count = Utils.get_clmn_count(self.ww)
        row, col = 0, 0

        Thumb.calculate_size()

        cut = self.order_items[self.offset:self.offset + self.limit]

        for order_item in cut:
    
            if os.path.isdir(order_item.src):

                wid = ListItem(
                    text=os.path.basename(order_item.src),
                    svg_path=Static.FOLDER_SVG
                    )

                # wid = ThumbFolder(
                #     src=order_item.src,
                #     size=order_item.size,
                #     mod=order_item.mod,
                #     colors=order_item.colors,
                #     rating=order_item.rating,
                #     )

                # if os.path.ismount(order_item.src) or order_item.src == sys_disk:
                    # img_wid = wid.img_wid.findChild(QSvgWidget)
                    # img_wid.load(Static.HDD_SVG)


            else:

                wid = ListItem(
                    text=os.path.basename(order_item.src),
                    svg_path=Static.IMG_SVG
                )

            list_item = QListWidgetItem()
            list_item.setSizeHint(wid.sizeHint())

            self.addItem(list_item)
            self.setItemWidget(list_item, wid)

                # wid = Thumb(
                    # src=order_item.src,
                    # size=order_item.size,
                    # mod=order_item.mod,
                    # colors=order_item.colors,
                    # rating=order_item.rating,
                    # )

            # wid.select.connect(lambda w=wid: self.select_new_widget(w))
            # wid.open_in_view.connect(lambda w=wid: self.open_in_view(w))
            # self.grid_layout.addWidget(wid, row, col)

            # self.add_widget_data(wid, row, col)

            col += 1
            if col >= col_count:
                col = 0
                row += 1

        if not os.path.exists(JsonData.root):
            setattr(self, "no_images", PATH_NOT_EXISTS)

        elif not self.cell_to_wid:
            setattr(self, "no_images", NO_IMAGES)

        if hasattr(self, "no_images"):
            no_images = QLabel(text=getattr(self, "no_images"))
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0)

        self.order_()
        # self.select_after_list()

    def closeEvent(self, a0: QCloseEvent | None) -> None:

        try:
            self.loading_lbl.deleteLater()
        except RuntimeError:
            ...

        for i in self.tasks:
            i.should_run = False

        return super().closeEvent(a0)

    def resizeEvent(self, a0):
        try:
            Utils.center_win(self, self.loading_lbl)
        except RuntimeError:
            ...
        return super().resizeEvent(a0)