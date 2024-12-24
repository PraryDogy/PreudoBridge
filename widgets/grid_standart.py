import os
import traceback
from typing import Literal

import numpy as np
import sqlalchemy
from numpy import ndarray
from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QPixmap
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import QLabel
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import JsonData, Static, ThumbData
from database import CACHE, ColumnNames, Dbase, OrderItem
from fit_img import FitImg
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from ._finder_items import FinderItems, LoadingWid
from ._grid import Grid, Thumb, ThumbFolder
from ._grid_tools import GridTools

WARN_TEXT = "Нет изображений или нет подключения к диску"
TASK_NAME = "LOAD_IMAGES"
SQL_ERRORS = (IntegrityError, OperationalError)


class ImageData:
    __slots__ = ["src", "pixmap", "rating"]

    def __init__(self, src: str, pixmap: QPixmap, rating: int):
        self.src = src
        self.pixmap = pixmap
        self.rating = rating


class WorkerSignals(QObject):
    new_widget = pyqtSignal(ImageData)


class LoadImages(URunnable):
    def __init__(self, order_items: list[OrderItem]):
        super().__init__()

        self.signals_ = WorkerSignals()
        self.order_items = [
            i
            for i in order_items
            if i.type_ != Static.FOLDER_TYPE
        ]

    @URunnable.set_running_state
    def run(self):

        # чтобы не создавать пустую ДБ в пустых или папочных директориях

        if not self.order_items:
            return

        db = os.path.join(JsonData.root, Static.DB_FILENAME)
        self.dbase = Dbase()
        engine = self.dbase.create_engine(path=db)
        self.conn = engine.connect()

        try:
            self.main()
        except RuntimeError as e:
            Utils.print_error(parent=None, error=e)

    def main(self):
        self.process_order_items()
        self.process_removed_items()
        self.conn.close()

    def process_order_items(self):

        for order_item in self.order_items:
            
            try:
                self.create_image_data(order_item=order_item)

            except Exception as e:
                # Utils.print_error(parent=self, error=e)
                print(traceback.format_exc())
                continue

    def create_image_data(self, order_item: OrderItem):
        
        db_item, rating = GridTools.load_db_item(
            conn=self.conn,
            order_item=order_item,
        )

        if isinstance(db_item, int):
            # print("update", order_item.name)
            img_array = self.update_db_item(
                order_item=order_item,
                row_id=db_item
            )

        elif db_item is None:
            # print("insert", order_item.name)
            img_array = self.insert_db_item(
                order_item=order_item
            )
        
        elif isinstance(db_item, bytes):
            # print("already", order_item.name)
            img_array = Utils.bytes_to_array(
                blob=db_item
            )

        if isinstance(img_array, np.ndarray):

            pixmap = Utils.pixmap_from_array(
                image=img_array
            )

            image_data = ImageData(
                src=order_item.src,
                pixmap=pixmap,
                rating=rating
            )

            self.signals_.new_widget.emit(image_data)

    def load_db_item(self): ...

    def update_db_item(self, order_item: OrderItem, row_id: int) -> np.ndarray:

        bytes_img, img_array = self.get_bytes_ndarray(
            order_item=order_item
        )

        new_size, new_mod, new_resol = self.get_stats(
            order_item=order_item,
            img_array=img_array
        )

        values = {
            ColumnNames.NAME: order_item.name,
            ColumnNames.IMG: bytes_img,
            ColumnNames.SIZE: new_size,
            ColumnNames.MOD: new_mod,
            ColumnNames.RESOL: new_resol
        }

        q = sqlalchemy.update(CACHE).where(CACHE.c.id == row_id)
        q = q.values(**values)

        # пытаемся вставить запись в БД, но если не выходит
        # все равно отдаем изображение
        self.execute_query(
            query=q
        )

        return img_array


    def insert_db_item(self, order_item: OrderItem) -> np.ndarray:

        bytes_img, img_array = self.get_bytes_ndarray(
            order_item=order_item
        )

        new_size, new_mod, new_resol = self.get_stats(
            order_item=order_item,
            img_array=img_array
        )

        values = {
            ColumnNames.IMG: bytes_img,
            ColumnNames.NAME: order_item.name,
            ColumnNames.TYPE: order_item.type_,
            ColumnNames.SIZE: new_size,
            ColumnNames.MOD: new_mod,
            ColumnNames.RATING: 0,
            ColumnNames.RESOL: new_resol,
            ColumnNames.CATALOG: ""
        }

        q = sqlalchemy.insert(CACHE)
        q = q.values(**values)

        # пытаемся вставить запись в БД, но если не выходит
        # все равно отдаем изображение
        self.execute_query(
            query=q
        )

        return img_array
    
    def get_bytes_ndarray(self, order_item: OrderItem):

        img_array = Utils.read_image(
            path=order_item.src
        )

        img_array = FitImg.start(
            image=img_array,
            size=ThumbData.DB_PIXMAP_SIZE
        )

        bytes_img = Utils.numpy_to_bytes(
            img_array=img_array
        )

        return bytes_img, img_array
    
    def get_stats(self, order_item: OrderItem, img_array: np.ndarray):

        stats = os.stat(order_item.src)
        height, width = img_array.shape[:2]

        new_size = int(stats.st_size)
        new_mod = int(stats.st_mtime)
        new_resol = f"{width}x{height}"

        return new_size, new_mod, new_resol
    
    def execute_query(self, query):
        try:
            self.conn.execute(query)
            self.conn.commit()
        except SQL_ERRORS as e:
            Utils.print_error(parent=self, error=e)
            self.conn.rollback()

    def process_removed_items(self):

        q = sqlalchemy.select(CACHE.c.id, CACHE.c.name)
        res = self.conn.execute(q).fetchall()

        order_items = [
            i.name
            for i in self.order_items
        ]

        del_items: list[int] = []

        for id, name in res:
            if name not in order_items:
                del_items.append(id)

        for id_ in del_items:

            q = sqlalchemy.delete(CACHE)
            q = q.where(CACHE.c.id == id_)

            try:
                self.conn.execute(q)

            except SQL_ERRORS as e:
                Utils.print_error(parent=self, error=e)
                self.conn.rollback()
                continue

        try:
            self.conn.commit()

        except SQL_ERRORS as e:
            Utils.print_error(parent=self, error=e)
            self.conn.rollback()


class GridStandart(Grid):
    def __init__(self, width: int, prev_path: str = None):

        super().__init__(
            width=width,
            prev_path=prev_path
        )

        self.order_items: list[OrderItem] = []
        self.tasks: list[LoadImages] = []

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

        SignalsApp.instance.bar_bottom_cmd.emit(
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

                wid = ThumbFolder(
                    src=order_item.src,
                    size=order_item.size,
                    mod=order_item.mod,
                    rating=order_item.rating,
                    )

                if os.path.ismount(order_item.src) or order_item.src == sys_disk:
                    img_wid = wid.img_frame.findChild(QSvgWidget)
                    img_wid.load(Static.HDD_SVG)


            else:
                wid = Thumb(
                    src=order_item.src,
                    size=order_item.size,
                    mod=order_item.mod,
                    rating=order_item.rating,
                    )

            wid.clicked_.connect(
                lambda w=wid: self.select_one_wid(wid=w)
            )
        
            wid.control_clicked.connect(
                lambda w=wid: self.control_clicked(wid=w)
            )

            wid.shift_clicked.connect(
                lambda w=wid: self.shift_clicked(wid=w)
            )

            wid.open_in_view.connect(
                lambda w=wid: self.open_in_view(wid=w)
            )

            wid.mouse_moved.connect(
                lambda w=wid: self.drag_event(wid=w)
            )

            self.add_widget_data(
                wid=wid,
                row=row,
                col=col
            )

            self.grid_layout.addWidget(wid, row, col)

            col += 1
            if col >= col_count:
                col = 0
                row += 1

        if self.cell_to_wid:
            self.start_load_images(cut)

        elif not os.path.exists(JsonData.root):
            setattr(self, "no_images", WARN_TEXT)

        elif not self.cell_to_wid:
            setattr(self, "no_images", WARN_TEXT)

        if hasattr(self, "no_images"):
            no_images = QLabel(text=getattr(self, "no_images"))
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0)

        self.order_()
        self.select_after_list()
        
    def start_load_images(self, cut_order_items: list[OrderItem]):
        self.load_images_task_ = LoadImages(order_items=cut_order_items)
        self.load_images_task_.set_name(text=TASK_NAME)
        cmd_ = lambda image_data: self.set_pixmap(image_data)
        self.load_images_task_.signals_.new_widget.connect(cmd_)
        UThreadPool.start(self.load_images_task_)
    
    def set_pixmap(self, image_data: ImageData):

        widget = Thumb.path_to_wid.get(image_data.src)

        if isinstance(widget, Thumb):

            if isinstance(image_data.pixmap, QPixmap):
                widget.set_pixmap(pixmap=image_data.pixmap)

            if isinstance(image_data.rating, int):
                widget.set_rating_cmd(rating=image_data.rating)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        
        for task in UThreadPool.current:
            if task.get_name() == TASK_NAME:
                task.should_run = False

        return super().closeEvent(a0)

    def resizeEvent(self, a0):
        Utils.center_win(self, self.loading_lbl)
        return super().resizeEvent(a0)