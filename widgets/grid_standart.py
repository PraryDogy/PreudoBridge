import os
from typing import Literal

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

from ._finder_items import FinderItems, ImageData, LoadingWid
from ._grid import Grid, Thumb, ThumbFolder

MAX_QUERIES = 10
WARN_TEXT = "Нет изображений или нет подключения к диску"
TASK_NAME = "LOAD_IMAGES"


class WorkerSignals(QObject):
    new_widget = pyqtSignal(ImageData)


class LoadImages(URunnable):
    def __init__(self, order_items: list[OrderItem]):
        super().__init__()

        self.signals_ = WorkerSignals()
        self.order_items = order_items

        # self.remove_db_images: list[tuple[str, str]] = []
        # self.db_items: dict[tuple, str] = {}
        # self.insert_count_data: list[tuple[sqlalchemy.Insert, str, ndarray]] = []

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
        self.get_db_dataset()
        self.compare_db_and_finder_items()

        # remove images необходимо выполнять перед insert_queries_cmd
        # т.к. у нас sqlalchemy.update отсутствует
        # и обновление происходит через удаление и добавление заново
        self.remove_images()
        self.create_new_images()
        self.insert_count_cmd()

        self.conn.close()

    def new_meth(self):

        for item in self.order_items:
            
            db_item = self.load_db_item(
                item=item,
                where_stmts=[CACHE.c.src == item.src]
            )

            if db_item:

                was_modified = self.was_modified(
                    item=item,
                    db_item=db_item,
                    attrs=[ColumnNames.MOD]
                )

                if was_modified:

                    try:
                        pixmap = self.db_update(
                            db_item=db_item
                        )

                        image_data = ImageData(
                            src=item.src,
                            pixmap=pixmap
                        )

                        self.signals_.new_widget.emit(image_data)

                    except Exception as e:
                        Utils.print_error(parent=self, error=e)
                        continue

                elif not was_modified:

                    pixmap = self.src_load_img(
                        db_item=db_item
                    )

                    image_data = ImageData(
                        src=item.src,
                        pixmap=pixmap
                    )

                    self.signals_.new_widget.emit(image_data)
            
            elif not db_item:
                ...


    
    def load_db_item(self, where_stmts: list):

        q = sqlalchemy.select(
            CACHE.c.src,
            CACHE.c.hash_path,
            CACHE.c.size,
            CACHE.c.mod
        )

        for stmt in where_stmts:
            q = q.where(stmt)

        return self.conn.execute(q).first()

    def was_modifired(self, item: OrderItem, db_item: tuple, attrs: list[str]):

        src, hash_path, size, mod = db_item

        db_item_dict = {
            ColumnNames.SRC: src,
            ColumnNames.SIZE: size,
            ColumnNames.MOD: mod
        }

        for attr in attrs:
            if getattr(item, attr) != db_item_dict.get(attr):
                return True

        return False

    def db_update(self, db_item: tuple) -> QPixmap:

        src, hash_path, size, mod = db_item
        os.remove(hash_path)

        stats = os.stat(src)
        new_size = stats.st_size
        new_mod = stats.st_mtime

        new_hash_path = Utils.create_hash_path(
            src=src
        )

        img_array = Utils.read_image(
            full_src=src
        )
        
        h_, w_ = img_array.shape[:2]
        new_resol = f"{w_}x{h_}"

        values = {
            ColumnNames.HASH_PATH: new_hash_path,
            ColumnNames.SIZE: new_size,
            ColumnNames.MOD: new_mod,
            ColumnNames.RESOL: new_resol
        }

        q = sqlalchemy.update(CACHE).where(CACHE.c.src == src)
        q = q.values(**values)
        self.conn.execute(q)
        self.conn.commit()

        small_img_array = FitImg.start(
            image=img_array, 
            size=ThumbData.DB_PIXMAP_SIZE
        )

        Utils.write_image_hash(
            output_path=new_hash_path,
            array_img=small_img_array
        )

        return Utils.pixmap_from_array(image=small_img_array)


    def src_load_img(self, db_item: tuple):
        src, hash_path, size, mod = db_item
        img_array = Utils.read_image_hash(
            src=src
        )

        return Utils.pixmap_from_array(image=img_array)


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