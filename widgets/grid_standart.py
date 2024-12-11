import os

import sqlalchemy
from numpy import ndarray
from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QPixmap
from PyQt5.QtWidgets import QLabel
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import FOLDER_TYPE, HDD_SVG, IMG_EXT, JsonData, ThumbData, GRAY_UP_BTN
from database import CACHE, Dbase, OrderItem
from fit_img import FitImg
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from ._grid import Grid
from ._thumb import Thumb, ThumbFolder

MAX_QUERIES = 10


class ImageData:
    __slots__ = ["src", "pixmap"]

    def __init__(self, src: str, pixmap: QPixmap):
        self.src: str = src
        self.pixmap: QPixmap = pixmap


class WorkerSignals(QObject):
    new_widget = pyqtSignal(ImageData)
    finished_ = pyqtSignal(list)


class Flag:
    can_run = False



class LoadImages(URunnable):
    def __init__(self, order_items: list[OrderItem]):
        super().__init__()

        self.signals_ = WorkerSignals()
        self.finder_items: list[tuple[int, int, int]] = [
            (order_item.src, order_item.size, order_item.mod)
            for order_item in order_items
            if order_item.type_ != FOLDER_TYPE
            ]

        self.remove_db_images: list[tuple[str, str]] = []
        self.db_items: dict[tuple, str] = {}
        self.insert_count_data: list[tuple[sqlalchemy.Insert, str, ndarray]] = []

        self.conn = Dbase.engine.connect()

    @URunnable.set_running_state
    def run(self):
        self.get_db_dataset()
        self.compare_db_and_finder_items()

        # remove images необходимо выполнять перед insert_queries_cmd
        # т.к. у нас sqlalchemy.update отсутствует
        # и обновление происходит через удаление и добавление заново
        self.remove_images()
        self.create_new_images()
        self.insert_count_cmd()

        self.conn.close()

        # if self.should_run:
        #     print("завершено по доброй воле")
        # else:
        #     print("принудительно")

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

        # order items имеют другую сортировку нежели order_items?


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
                hash_path = Utils.get_hash_path(src)
                args = src, hash_path, size, mod, resol

                stmt = self.get_insert_stmt(*args)
                self.insert_count_data.append((stmt, hash_path, small_img_array))

                try:
                    self.signals_.new_widget.emit(ImageData(src, pixmap))
                except RuntimeError:
                    ...
                # SignalsApp.all_.progressbar_cmd.emit({"cmd": "plus_one"})

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
        name = os.path.basename(src)
        type_ = os.path.splitext(name)[-1]

        args = (src, hash_path, name, type_, size, mod, resol)
        values_ = Dbase.get_cache_values(*args)

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


class LoadFinder(URunnable):
    def __init__(self):
        super().__init__()
        self.signals_ = WorkerSignals()
        self.db_color_rating: dict[str, list] = {}
        self.order_items: list[OrderItem] = []

    @URunnable.set_running_state
    def run(self):
        try:
            self.get_color_rating()
            self.get_items()
            self.order_items = OrderItem.order_items(self.order_items)

        except (PermissionError, FileNotFoundError, NotADirectoryError) as e:
            Utils.print_error(self, e)
            self.order_items = []
        
        self.signals_.finished_.emit(self.order_items)

    def get_color_rating(self):
        q = sqlalchemy.select(CACHE.c.src, CACHE.c.colors, CACHE.c.rating)
        q = q.where(CACHE.c.root == JsonData.root)
  
        with Dbase.engine.connect() as conn:
            res = conn.execute(q).fetchall()

            self.db_color_rating = {
                src: [colors, rating]
                for src, colors, rating in res
            }

    def get_items(self) -> list:

        with os.scandir(JsonData.root) as entries:

            for entry in entries:

                if entry.name.startswith("."):
                    continue

                if entry.is_dir() or entry.name.endswith(IMG_EXT):
                    try:
                        stats = entry.stat()
                    except (PermissionError, FileNotFoundError, OSError):
                        continue

                    size = stats.st_size
                    mod = stats.st_mtime
                    colors = ""
                    rating = 0

                    db_item = self.db_color_rating.get(entry.path)

                    if db_item:
                        colors, rating = db_item

                    item = OrderItem(entry.path, size, mod, colors, rating)
                    self.order_items.append(item)


class GridStandart(Grid):
    def __init__(self, width: int):
        super().__init__(width)

        self.order_items: list[OrderItem] = []
        self.tasks: list[LoadImages] = []

        self.offset = 0
        self.limit = 100

        self.loading_lbl = QLabel(text="Загрузка...", parent=self)
        self.loading_lbl.setStyleSheet(
            f"""
                background: {GRAY_UP_BTN};
                border-radius: 4px;
                padding: 2px;
            """
        )

        # self.window()
        self.move(100, 100)
        self.show()

        self.finder_task = LoadFinder()
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

        self.loading_lbl.deleteLater()
        self.order_items = order_items
        self.total = len(order_items)

        SignalsApp.all_.path_labels_cmd.emit(
            {"src": JsonData.root, "total": self.total}
        )

        self.create_sorted_grid()
        self.set_main_wid()

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
                    colors=order_item.colors,
                    rating=order_item.rating,
                    )

                if (
                    os.path.ismount(order_item.src)
                    or
                    order_item.src == sys_disk
                ):
                    wid.img_wid.load(HDD_SVG)


            else:
                wid = Thumb(
                    src=order_item.src,
                    size=order_item.size,
                    mod=order_item.mod,
                    colors=order_item.colors,
                    rating=order_item.rating,
                    )

            wid.select.connect(lambda w=wid: self.select_new_widget(w))
            wid.open_in_view.connect(lambda w=wid: self.open_in_view(w))
            self.grid_layout.addWidget(wid, row, col)

            self.add_widget_data(wid, row, col)

            col += 1
            if col >= col_count:
                col = 0
                row += 1

        if self.cell_to_wid:
            self.start_load_images(cut)

        elif not os.path.exists(JsonData.root):
            t = f"{JsonData.root}\nТакой папки не существует\nПроверьте подключение к сетевому диску"
            setattr(self, "no_images", t)

        else:
            t = f"{JsonData.root}\nНет изображений"
            setattr(self, "no_images", t)

        if hasattr(self, "no_images"):
            no_images = QLabel(t)
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0)

        self.order_()
        self.select_after_list()
        
    def start_load_images(self, cut_order_items: list[OrderItem]):
        task_ = LoadImages(order_items=cut_order_items)
        self.tasks.append(task_)
        cmd_ = lambda image_data: self.set_pixmap(image_data)
        task_.signals_.new_widget.connect(cmd_)
        UThreadPool.start(task_)
    
    def set_pixmap(self, image_data: ImageData):
        widget = Thumb.path_to_wid.get(image_data.src)
        if isinstance(widget, Thumb):
            if isinstance(image_data.pixmap, QPixmap):
                widget.set_pixmap(pixmap=image_data.pixmap)

    def closeEvent(self, a0: QCloseEvent | None) -> None:

        for i in self.tasks:
            i.should_run = False

        return super().closeEvent(a0)
