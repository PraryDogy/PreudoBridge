import os

import sqlalchemy
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QPixmap
from PyQt5.QtWidgets import QLabel
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import IMG_SIZE, Config, JsonData
from database import CACHE, STATS, Engine
from fit_img import FitImg
from signals import SIGNALS
from utils import Utils

from ._grid import Grid, Thumb
from ._thumb import ThumbFolder


# Если родительский класс запущенного треда будет закрыт
# Тред получит сигнал стоп и безопасно завершится
class Threads:
    all: list = []


# Данный тред получает на вхол словарик {(путь, размер, дата): виджет для Pixmap}
# по ключам ищем существующие изображения в БД
# если есть - подгружаем в сетку
# если нет - считываем, делаем запись в БД, подгружаем в сетку


class ImageData:
    def __init__(self, src: str, size: int, mod: int, pixmap: QPixmap):
        self.src: str = src
        self.size: int = size
        self.mod: int = mod
        self.pixmap: QPixmap = pixmap


class LoadImages(QThread):

    # передает обратно (путь, размер, дата): PIXMAP
    # чтобы в основном потоке в словарике найти виджет и применить изображение
    new_widget = pyqtSignal(ImageData)

    # флаг проверяется в цикле и если False то цикл прерывается
    stop_thread = pyqtSignal()

    # не используется
    _finished = pyqtSignal()
    
    def __init__(self, src_size_mod: list[tuple]):
        super().__init__()

        self.src_size_mod: list[tuple] = src_size_mod
        self.remove_db_images: list = []
        self.db_images: dict[tuple, bytearray] = {}
        self.flag = True
        self.db_size: int = 0

        self.stop_thread.connect(self.stop_thread_cmd)
        self.conn = Engine.engine.connect()

    def run(self):
        self.get_db_size()

        self.get_db_images()
        self.load_already_images()
        self.create_new_images()
        self.remove_images()

        self.update_db_size()

        self.conn.close()
        self._finished.emit()

    def get_db_size(self):
        sel_size = sqlalchemy.select(STATS.c.size).where(STATS.c.name == "main")
        self.db_size: int = self.conn.execute(sel_size).scalar() or 0

    def update_db_size(self):
        upd_size = sqlalchemy.update(STATS).where(STATS.c.name == "main").values(size=self.db_size)
        try:
            self.conn.execute(upd_size)
            self.conn.commit()
        except OperationalError as e:
            Utils.print_error(self, e)

    def get_db_images(self):
        q = sqlalchemy.select(CACHE.c.img, CACHE.c.src, CACHE.c.size, CACHE.c.mod)
        q = q.where(CACHE.c.root == JsonData.root)
        res = self.conn.execute(q).fetchall()

        self.db_images: dict[tuple, bytearray] = {
            (src, size, mod): img
            for img, src, size,  mod in res
            }

    def load_already_images(self):
        for (db_src, db_size, db_mod), db_byte_img in self.db_images.items():

            if not self.flag:
                break

            if (db_src, db_size, db_mod) in self.src_size_mod:
                pixmap: QPixmap = Utils.pixmap_from_bytes(db_byte_img)
                self.new_widget.emit(ImageData(db_src, db_size, db_mod, pixmap))
                self.src_size_mod.remove((db_src, db_size, db_mod))
            else:
                self.remove_db_images.append(db_src)
                self.db_size -= len(db_byte_img)

    def create_new_images(self):
        SIGNALS.progressbar_value.emit(len(self.src_size_mod))
        progress_count = 0
        insert_count = 0

        for src, size, mod in self.src_size_mod:

            if not self.flag:
                break

            if os.path.isdir(src):
                continue

            img_array = Utils.read_image(src)
            img_array = FitImg.start(img_array, IMG_SIZE)
            img_bytes: bytes = Utils.image_array_to_bytes(img_array)

            pixmap = Utils.pixmap_from_array(img_array)

            if not isinstance(img_bytes, bytes):
                continue

            if isinstance(pixmap, QPixmap):

                self.new_widget.emit(ImageData(src, size, mod, pixmap))

            try:
                insert_stmt = self.get_insert_stmt(img_bytes, src, size, mod)
                self.conn.execute(insert_stmt)

                self.db_size += len(img_bytes)

                insert_count += 1
                if insert_count >= 10:
                    self.conn.commit()
                    insert_count = 0

                SIGNALS.progressbar_value.emit(progress_count)
                progress_count += 1

            except IntegrityError as e:
                Utils.print_error(self, e)
                continue

            except OperationalError as e:
                Utils.print_error(self, e)
                self.stop_thread_cmd()
                break

        if insert_count > 0:
            try:
                self.conn.commit()
            except (IntegrityError, OperationalError) as e:
                Utils.print_error(self, e)

        # 1 милилон = скрыть прогресс бар согласно его инструкции
        SIGNALS.progressbar_value.emit(1000000)

    def get_insert_stmt(self, img_bytes, src, size, mod):
        insert = sqlalchemy.insert(CACHE)
        return insert.values(
            img = img_bytes,
            src = src,
            root = os.path.dirname(src),
            size = size,
            mod = mod,
            catalog = "",
            colors = "",
            rating = 0
            )

    def remove_images(self):
        try:
            for src in self.remove_db_images:
                q = sqlalchemy.delete(CACHE).where(CACHE.c.src == src)
                self.conn.execute(q)
            self.conn.commit()
        except OperationalError as e:
            Utils.print_error(self, e)
            return

    def stop_thread_cmd(self):
        self.flag = False


class LoadFinder(QThread):
    _finished = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.db_data: dict[str, list] = {}
        self.finder_items: list[tuple] = []

    def run(self):
        try:
            self.get_db_data()
            self.get_items()
        except (PermissionError, FileNotFoundError) as e:
            Utils.print_error(self, e)
            self.finder_items: list = []
        
        self._finished.emit(self.finder_items)

    def get_db_data(self):
        q = sqlalchemy.select(CACHE.c.src, CACHE.c.colors, CACHE.c.rating)
        q = q.where(CACHE.c.root == JsonData.root)
  
        with Engine.engine.connect() as conn:
            res = conn.execute(q).fetchall()
            self.db_data = {src: [colors, rating] for src, colors, rating in res}

    def get_items(self) -> list:
        for name in os.listdir(JsonData.root):

            src: str = os.path.join(JsonData.root, name)

            try:
                stats = os.stat(src)
                size = stats.st_size
                mod = stats.st_mtime
                filetype = os.path.splitext(name)[1]

                if self.db_data.get(src):
                    colors = self.db_data.get(src)[0]
                    rating = self.db_data.get(src)[1]
                else:
                    colors = ""
                    rating = 0

            except (PermissionError, FileNotFoundError, OSError):
                continue

            # ПОРЯДОК КОРТЕЖА РАВЕН ORDER
            # SRC по которой нет сортировки идет в конце

            if src.lower().endswith(Config.IMG_EXT):
                self.finder_items.append((name, size, mod, filetype, colors, rating, src))
                continue

            if os.path.isdir(src):
                self.finder_items.append((name, size, mod, filetype, colors, rating, src))


class GridStandart(Grid):
    def __init__(self, width: int):
        super().__init__(width)
        # делаем os listdir обход и по сигналу finished
        # запустится создание сетки
        # в конце создания запустится подгрузка изображений
        self.finder_thread = LoadFinder()
        self.finder_thread._finished.connect(self.create_grid)
        self.finder_thread.start()

    def create_grid(self, finder_items: list):
        src_size_mod: list[tuple] = []

        col_count = Utils.get_clmn_count(self.ww)
        row, col = 0, 0

        for name, size, mod, type, colors, rating, src in finder_items:

            if os.path.isdir(src):
                wid = ThumbFolder(src, 0, 0, {})
                pixmap = QPixmap("images/folder_210.png")
                wid.set_pixmap(pixmap)
                wid.set_colors_from_db("")

            else:
                wid = Thumb(src, size, mod, self.path_to_wid)
                pixmap = QPixmap("images/file_210.png")
                wid.set_pixmap(pixmap)
                wid.set_colors_from_db(colors)
                wid.set_rating_from_db(rating)
                wid.move_to_wid.connect(lambda w: self.select_new_widget(w))
                src_size_mod.append((src, size, mod))

            wid.clicked.connect(lambda w=wid: self.select_new_widget(w))
            self.grid_layout.addWidget(wid, row, col)

            self.add_widget_data(wid, row, col)

            col += 1
            if col >= col_count:
                col = 0
                row += 1

        if self.cell_to_wid:
            self.start_load_images(src_size_mod)

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

        self.add_row_spacer(row + 1, 0)
        self.sort_grid()

    def stop_threads(self):
        for i in Threads.all:
            i: LoadImages
            i.stop_thread.emit()

            if i.isFinished():
                Threads.all.remove(i)

    def start_load_images(self, src_size_mod: list[tuple]):
        thread = LoadImages(src_size_mod)
        thread.new_widget.connect(lambda image_data: self.set_pixmap(image_data))
        Threads.all.append(thread)
        thread.start()
    
    def set_pixmap(self, image_data: ImageData):
        widget = self.path_to_wid.get(image_data.src)
        if isinstance(widget, Thumb):
            if isinstance(image_data.pixmap, QPixmap):
                widget.set_pixmap(image_data.pixmap)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        # когда убивается этот виджет, все треды безопасно завершатся
        self.stop_threads()
        return super().closeEvent(a0)