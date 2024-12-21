import os

import sqlalchemy
from numpy import ndarray
from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QPixmap
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import QLabel
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import JsonData, Static, ThumbData
from database import CACHE, Dbase, OrderItem
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
        self.finder_items: list[tuple[int, int, int]] = [
            (order_item.src, order_item.size, order_item.mod)
            for order_item in order_items
            if order_item.type_ != Static.FOLDER_TYPE
            ]

        self.remove_db_images: list[tuple[str, str]] = []
        self.db_items: dict[tuple, str] = {}
        self.insert_count_data: list[tuple[sqlalchemy.Insert, str, ndarray]] = []

        self.conn = Dbase.engine.connect()

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

    def get_db_dataset(self):

        db_items: list[tuple] = []

        for src, size, mod in self.finder_items:
            q = sqlalchemy.select(
                CACHE.c.src,
                CACHE.c.hash_path,
                CACHE.c.size,
                CACHE.c.mod
                )
            q = q.where(CACHE.c.src==src)
            res = self.conn.execute(q).first()

            if res:
                db_items.append(res)

        self.db_items: dict[tuple, str] = {
            (src, size, mod): hash_path
            for src, hash_path, size, mod in db_items
            if src is not None
            }

    def compare_db_and_finder_items(self):
        for (db_src, db_size, db_mod), hash_path in self.db_items.items():

            if not self.should_run:
                break

            if (db_src, db_size, db_mod) in self.finder_items:
                img = Utils.read_image_hash(hash_path)
                pixmap: QPixmap = Utils.pixmap_from_array(img)
                self.signals_.new_widget.emit(ImageData(db_src, pixmap))
                self.finder_items.remove((db_src, db_size, db_mod))

            else:
                self.remove_db_images.append((db_src, hash_path))

        # print("*" * 50)
        # print(self.finder_items)
        # print(self.db_items)
        # print("*" * 50)

    def create_new_images(self):
        insert_count = 0

        for src, size, mod in self.finder_items:


            if not self.should_run:
                break

            elif os.path.isdir(src):
                continue

            if insert_count == MAX_QUERIES:
                self.insert_count_cmd()
                self.insert_count_data.clear()
                insert_count = 0

            img_array = Utils.read_image(src)

            if img_array is not None:

                small_img_array = FitImg.start(img_array, ThumbData.DB_PIXMAP_SIZE)
                pixmap = Utils.pixmap_from_array(small_img_array)

                h_, w_ = img_array.shape[:2]
                resol = f"{w_}x{h_}"
                hash_path = Utils.create_hash_path(src)
                args = src, hash_path, size, mod, resol

                stmt = self.get_insert_stmt(*args)
                self.insert_count_data.append((stmt, hash_path, small_img_array))

                self.signals_.new_widget.emit(ImageData(src, pixmap))

                insert_count += 1

    def insert_count_cmd(self):
        for stmt, hash_path, img_array in self.insert_count_data:

            try:
                self.conn.execute(stmt)

            except IntegrityError as e:
                self.conn.rollback()
                Utils.print_error(self, e)
                continue

            except OperationalError as e:
                self.conn.rollback()
                Utils.print_error(self, e)
                self.should_run = False
                return None

        self.conn.commit()

        for stmt_, hash_path, img_array in self.insert_count_data:
            Utils.write_image_hash(hash_path, img_array)

        return True

    def get_insert_stmt(
            self,
            src: str,
            hash_path: str,
            size: int,
            mod: int,
            resol: str,
            )  -> sqlalchemy.Insert:

        src = os.sep + src.strip().strip(os.sep)
        values_ = Dbase.get_cache_values(src, hash_path, size, mod, resol)

        return sqlalchemy.insert(CACHE).values(**values_)

    def remove_images(self):

        for src, hash_path in self.remove_db_images:

            try:
                q = sqlalchemy.delete(CACHE).where(CACHE.c.src == src)
                self.conn.execute(q)

            except IntegrityError as e:
                self.conn.rollback()
                Utils.print_error(self, e)
                continue

            except OperationalError as e:
                self.conn.rollback()
                Utils.print_error(self, e)
                return None

        self.conn.commit()

        for src, hash_path in self.remove_db_images:
            try:
                os.remove(hash_path)
            except (FileNotFoundError):
                ...

        return True


class GridStandart(Grid):
    def __init__(self, width: int):
        super().__init__(width)

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

        SignalsApp.all_.bar_bottom_cmd.emit(
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

            coords = (row, col)

            wid.clicked_.connect(
                lambda c=coords: self.select_one_wid(coords=c)
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