import os
from typing import Literal

import sqlalchemy
from numpy import ndarray
from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QPixmap
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import QLabel
from sqlalchemy.exc import IntegrityError, OperationalError

import numpy as np
from cfg import JsonData, Static, ThumbData
from database import CACHE, ColumnNames, Dbase, OrderItem
from fit_img import FitImg
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from ._finder_items import FinderItems, ImageData, LoadingWid
from ._grid import Grid, Thumb, ThumbFolder

MAX_QUERIES = 10
WARN_TEXT = "Нет изображений или нет подключения к диску"
TASK_NAME = "LOAD_IMAGES"
NEED_UPDATE = "need_update"
BYTES_IMG = "bytes_img"
ARRAY_IMG = "array_img"


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

        db = os.path.join(JsonData.root, Static.DB_FILENAME)
        self.dbase = Dbase()
        engine = self.dbase.create_engine(path=db)
        self.conn = engine.connect()

    @URunnable.set_running_state
    def run(self):
        try:
            self.main()
        except RuntimeError as e:
            Utils.print_error(parent=None, error=e)

    def main(self):
        self.process_order_items()
        self.conn.close()

    def process_order_items(self):

        for order_item in self.order_items:
            
            try:
                pixmap = self.create_pixmap(
                    order_item=order_item
                )

                image_data = ImageData(
                    src=order_item.src,
                    pixmap=pixmap
                )

                self.signals_.new_widget.emit(image_data)

            except Exception as e:
                Utils.print_error(parent=self, error=e)
                continue

    def create_pixmap(self, order_item: OrderItem):
        
        db_item = self.load_db_item(
            order_item=order_item,
        )

        if isinstance(db_item, int):

            img_array = self.update_db_item(
                order_item=order_item,
                row_id=db_item
            )

            # print("update", order_item.name)

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

            return pixmap

    def load_db_item(self, order_item: OrderItem) -> int | bytearray | None:
        """
        Загружает элемент из базы данных на основе имени файла, даты изменения и размера.

        Логика работы:
        1. Если запись найдена по имени файла:
        - Если дата изменения отличается, возвращается ID записи для обновления.
        - Если дата изменения совпадает, возвращается изображение в виде байт.
        2. Если запись не найдена по имени файла:
        - Ищется запись по дате изменения и размеру.
        - Если найдена, возвращается ID записи для обновления.
        - Если не найдена, возвращается None.

        :param order_item: Объект OrderItem, содержащий информацию о файле.
        :return: ID записи (int), изображение (bytearray) или None, если запись не найдена.
        """

        select_stmt = sqlalchemy.select(
            CACHE.c.id,
            CACHE.c.img,
            CACHE.c.size,
            CACHE.c.mod
        )

        # Проверка по имени файла
        where_stmt = select_stmt.where(CACHE.c.name == order_item.name)
        res_by_src = self.conn.execute(where_stmt).mappings().first()

        # Запись найдена
        if res_by_src:
            # Дата изменения в order_item и записи БД не совпадают
            if res_by_src.get(ColumnNames.MOD) != order_item.mod:
                # Нужно обновить запись БД
                return res_by_src.get(ColumnNames.ID)
            # Записи совпадают, возвращаем изображение bytearray
            return res_by_src.get(ColumnNames.IMG)

        # Запись по имени файла не найдена, возможно файл был переименован,
        # но содержимое файла не менялось
        # Пытаемся найти в БД запись по размеру и дате изменения order_item
        and_stmt = sqlalchemy.and_(
            CACHE.c.mod == order_item.mod,
            CACHE.c.size == order_item.size
        )
        where_and_stmt = select_stmt.where(and_stmt)
        res_by_mod = self.conn.execute(where_and_stmt).mappings().first()

        # Если запись найдена, значит файл действительно был переименован
        # возвращаем ID для обновления записи
        if res_by_mod:
            return res_by_mod.get(ColumnNames.ID)

        # ничего не найдено
        return None

    def update_db_item(self, order_item: OrderItem, row_id: int) -> np.ndarray:

        bytes_img, img_array = self.get_bytes_ndarray(
            order_item=order_item
        )

        new_size, new_mod, new_resol = self.get_stats(
            order_item=order_item,
            img_array=img_array
        )

        values = {
            ColumnNames.IMG: bytes_img,
            ColumnNames.SIZE: new_size,
            ColumnNames.MOD: new_mod,
            ColumnNames.RESOL: new_resol
        }

        q = sqlalchemy.update(CACHE).where(CACHE.c.id == row_id)
        q = q.values(**values)

        self.conn.execute(q)
        self.conn.commit()

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

        self.conn.execute(q)
        self.conn.commit()

        return img_array
    
    def get_bytes_ndarray(self, order_item: OrderItem):

        img_array = Utils.read_image(
            full_src=order_item.src
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

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        
        for task in UThreadPool.current:
            if task.get_name() == TASK_NAME:
                task.should_run = False

        return super().closeEvent(a0)

    def resizeEvent(self, a0):
        Utils.center_win(self, self.loading_lbl)
        return super().resizeEvent(a0)