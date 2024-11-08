import os

import sqlalchemy
from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QPixmap
from PyQt5.QtWidgets import QLabel
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import FOLDER, IMG_EXT, MAX_SIZE, JsonData
from database import CACHE, Dbase, OrderItem
from fit_img import FitImg
from signals import SignalsApp
from utils import Threads, URunnable, Utils

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
    _finished = pyqtSignal(list)


class LoadImages(URunnable):
    def __init__(self, order_items: list[OrderItem]):
        super().__init__()

        self.worker_signals = WorkerSignals()

        self.finder_items: list[tuple[int, int, int]] = [
            (order_item.src, order_item.size, order_item.mod)
            for order_item in order_items
            if order_item.type_ != FOLDER
            ]

        self.remove_db_images: list[tuple[str, str]] = []
        self.db_items: dict[tuple, str] = {}
        self.insert_queries: list[sqlalchemy.Insert] = []

    def run(self):
        self.set_is_running(True)

        self.get_db_dataset()
        self.compare_db_and_finder_items()

        ln_finder_items = len(self.finder_items)
        SignalsApp.all.progressbar_cmd.emit("max " + str(ln_finder_items))
        SignalsApp.all.progressbar_cmd.emit(0)
        SignalsApp.all.progressbar_cmd.emit("show")

        # remove images необходимо выполнять перед insert_queries_cmd
        # т.к. у нас sqlalchemy.update отсутствует
        # и обновление происходит через удаление и добавление заново
        self.remove_images()
        self.create_new_images()
        self.insert_queries_cmd()

        self.set_is_running(False)
        SignalsApp.all.progressbar_cmd.emit("hide")

    def get_db_dataset(self):

        with Dbase.engine.connect() as conn:

            q = sqlalchemy.select(
                CACHE.c.src,
                CACHE.c.hash_path,
                CACHE.c.size,
                CACHE.c.mod
                ).where(
                    CACHE.c.root == JsonData.root
                    )
            res = conn.execute(q).fetchall()

        self.db_items: dict[tuple, str] = {
            (src, size, mod): hash_path
            for src, hash_path, size, mod in res
            }

    def compare_db_and_finder_items(self):
        for (db_src, db_size, db_mod), hash_path in self.db_items.items():

            if not self.is_should_run():
                break

            if (db_src, db_size, db_mod) in self.finder_items:
                img = Utils.read_image_hash(hash_path)
                pixmap: QPixmap = Utils.pixmap_from_array(img)
                self.worker_signals.new_widget.emit(ImageData(db_src, pixmap))
                self.finder_items.remove((db_src, db_size, db_mod))

            else:
                self.remove_db_images.append((db_src, hash_path))

    def create_new_images(self):
        progress_count = 0
        insert_count = 0

        for src, size, mod in self.finder_items:

            if not self.is_should_run():
                break

            elif os.path.isdir(src):
                continue

            if insert_count == MAX_QUERIES:
                self.insert_queries_cmd()
                self.insert_queries.clear()
                insert_count = 0

            img_array = Utils.read_image(src)

            if img_array is not None:

                small_img_array = FitImg.start(img_array, MAX_SIZE)
                pixmap = Utils.pixmap_from_array(small_img_array)

                hashed_path = Utils.get_hash_path(src)
                Utils.write_image_hash(
                    output_path=hashed_path,
                    array_img=small_img_array
                    )

                stmt = self.get_insert_stmt(src, hashed_path, size, mod)
                self.insert_queries.append(stmt)

                self.worker_signals.new_widget.emit(ImageData(src, pixmap))
                SignalsApp.all.progressbar_cmd.emit(progress_count)

                progress_count += 1
                insert_count += 1

    def insert_queries_cmd(self):

        with Dbase.engine.connect() as conn:

            for query in self.insert_queries:

                try:
                    conn.execute(query)
                
                except IntegrityError as e:
                    Utils.print_error(self, e)
                    continue

                except OperationalError as e:
                    Utils.print_error(self, e)
                    self.set_should_run(False)
                    return

            conn.commit()

    def get_insert_stmt(
            self,
            src: str,
            hashed_path: str,
            size: int,
            mod: int
            )  -> sqlalchemy.Insert:

        src = os.sep + src.strip().strip(os.sep)
        name = os.path.basename(src)
        type_ = os.path.splitext(name)[-1]

        values = {
            "src": src,
            "hash_path": hashed_path,
            "root": os.path.dirname(src),
            "catalog": "",
            "name": name,
            "type_": type_,
            "size": size,
            "mod": mod,
            "colors": "",
            "rating": 0
            }

        return sqlalchemy.insert(CACHE).values(**values)

    def remove_images(self):

        with Dbase.engine.connect() as conn:

            for src, hash_path in self.remove_db_images:
                print("удаляю", src)

                try:
                    q = sqlalchemy.delete(CACHE).where(CACHE.c.src == src)
                    conn.execute(q)
                except OperationalError as e:
                    Utils.print_error(self, e)
                    return

            conn.commit()

        for src, hash_path in self.remove_db_images:
            os.remove(hash_path)


class LoadFinder(URunnable):
    def __init__(self):
        super().__init__()
        self.worker_signals = WorkerSignals()
        self.db_color_rating: dict[str, list] = {}
        self.order_items: list[OrderItem] = []

    def run(self):
        self.set_is_running(True)

        try:
            self.get_color_rating()
            self.get_items()
            self.order_items = OrderItem.order_items(self.order_items)
        except (PermissionError, FileNotFoundError) as e:
            Utils.print_error(self, e)
            self.order_items = []
        
        self.worker_signals._finished.emit(self.order_items)
        self.set_is_running(False)

    def get_color_rating(self):
        q = sqlalchemy.select(CACHE.c.src, CACHE.c.colors, CACHE.c.rating)
        q = q.where(CACHE.c.root == JsonData.root)
  
        with Dbase.engine.connect() as conn:
            res = conn.execute(q).fetchall()
            self.db_color_rating = {src: [colors, rating] for src, colors, rating in res}

    def get_items(self) -> list:

        for name in os.listdir(JsonData.root):

            src: str = os.path.join(JsonData.root, name)

            if name.startswith("."):
                continue

            if src.endswith(IMG_EXT) or os.path.isdir(src):

                try:
                    stats = os.stat(src)
                except (PermissionError, FileNotFoundError, OSError):
                    continue

                size = stats.st_size
                mod = stats.st_mtime
                colors = ""
                rating = 0

                db_item = self.db_color_rating.get(src)
                if db_item:
                    colors, rating = db_item

                item = OrderItem(src, size, mod, colors, rating)
                self.order_items.append(item)


class GridStandart(Grid):
    def __init__(self, width: int):
        super().__init__(width)

        self.pixmap_disk: QPixmap = QPixmap("images/disk_210.png")
        self.pixmap_folder: QPixmap = QPixmap("images/folder_210.png")
        self.pixmap_img: QPixmap = QPixmap("images/file_210.png")

        self.order_items: list[OrderItem] = []

        self.finder_task = LoadFinder()
        self.finder_task.worker_signals._finished.connect(self.create_sorted_grid)
        Threads.pool.start(self.finder_task)

    def create_sorted_grid(self, order_items: list[OrderItem]):

        self.order_items = order_items
        SignalsApp.all.create_path_labels.emit(JsonData.root, len(order_items))
        sys_disk = os.path.join(os.sep, "Volumes", "Macintosh HD")
        col_count = Utils.get_clmn_count(self.ww)
        row, col = 0, 0

        for order_item in self.order_items:
    
            if os.path.isdir(order_item.src):

                if os.path.ismount(order_item.src) or order_item.src == sys_disk:
                    folder_pixmap = self.pixmap_disk

                else:
                    folder_pixmap = self.pixmap_folder

                wid = ThumbFolder(
                    src=order_item.src,
                    size=order_item.size,
                    mod=order_item.mod,
                    colors=order_item.colors,
                    rating=order_item.rating,
                    pixmap=folder_pixmap
                    )

            else:
                wid = Thumb(
                    src=order_item.src,
                    size=order_item.size,
                    mod=order_item.mod,
                    colors=order_item.colors,
                    rating=order_item.rating,
                    pixmap=self.pixmap_img,
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
            self.start_load_images()

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

    def start_load_images(self):
        self.task_ = LoadImages(self.order_items)
        cmd_ = lambda image_data: self.set_pixmap(image_data)
        self.task_.worker_signals.new_widget.connect(cmd_)
        Threads.pool.start(self.task_)
    
    def set_pixmap(self, image_data: ImageData):
        widget = self.path_to_wid.get(image_data.src)
        if isinstance(widget, Thumb):
            if isinstance(image_data.pixmap, QPixmap):
                widget.set_pixmap(pixmap=image_data.pixmap)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        if hasattr(self, "task_") and self.task_.is_running():
            self.task_.set_should_run(False)
        return super().closeEvent(a0)