import os

import sqlalchemy
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QPixmap
from PyQt5.QtWidgets import QLabel
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import Config, JsonData
from database import CACHE, STATS, Engine
from fit_img import FitImg
from utils import Utils

from .grid import Grid, Thumb
from .thumb import ThumbFolder


# Если родительский класс запущенного треда будет закрыт
# Тред получит сигнал стоп и безопасно завершится
class Threads:
    all: list = []


# Данный тред получает на вхол словарик {(путь, размер, дата): виджет для Pixmap}
# по ключам ищем существующие изображения в БД
# если есть - подгружаем в сетку
# если нет - считываем, делаем запись в БД, подгружаем в сетку


class ImageData:
    def __init__(self, src: str, size: int, modified: int, pixmap: QPixmap):
        self.src: str = src
        self.size: int = size
        self.modified: int = modified
        self.pixmap: QPixmap = pixmap


class LoadImages(QThread):

    # передает обратно (путь, размер, дата): PIXMAP
    # чтобы в основном потоке в словарике найти виджет и применить изображение
    new_widget = pyqtSignal(ImageData)

    # отправляем в основное приложение чтобы показать прогресс
    progressbar_start = pyqtSignal(int)
    progressbar_value = pyqtSignal(int)

    # флаг проверяется в цикле и если False то цикл прерывается
    stop_thread = pyqtSignal()

    # не используется
    _finished = pyqtSignal()
    
    def __init__(self, src_size_mod: list[tuple]):
        super().__init__()

        self.src_size_mod: list[tuple] = src_size_mod
        self.remove_db_images: list = []
        self.db_images: dict[tuple: bytearray] = {}
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
        q = sqlalchemy.select(CACHE.c.img, CACHE.c.src, CACHE.c.size, CACHE.c.modified)
        q = q.where(CACHE.c.root == JsonData.root)
        res = self.conn.execute(q).fetchall()

        self.db_images: dict[tuple: bytearray] = {
            (src, size, modified): img
            for img, src, size,  modified in res
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
        self.progressbar_start.emit(len(self.src_size_mod))
        progress_count = 0
        insert_count = 0

        for src, size, modified in self.src_size_mod:

            if not self.flag:
                break

            if os.path.isdir(src):
                continue

            img_array = Utils.read_image(src)
            img_array = FitImg.start(img_array, Config.IMG_SIZE)
            img_bytes: bytes = Utils.image_array_to_bytes(img_array)
            pixmap = Utils.pixmap_from_array(img_array)

            if not isinstance(img_bytes, bytes):
                continue

            if isinstance(pixmap, QPixmap):
                self.new_widget.emit(ImageData(src, size, modified, pixmap))

            try:
                insert_stmt = self.get_insert_stmt(img_bytes, src, size, modified)
                self.conn.execute(insert_stmt)

                self.db_size += len(img_bytes)

                insert_count += 1
                if insert_count >= 10:
                    self.conn.commit()
                    insert_count = 0

                self.progressbar_value.emit(progress_count)
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
        self.progressbar_value.emit(1000000)

    def get_insert_stmt(self, img_bytes, src, size, modified):
        insert = sqlalchemy.insert(CACHE)
        return insert.values(
            img = img_bytes,
            src = src,
            root = os.path.dirname(src),
            size = size,
            modified = modified,
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
        self.db_data: dict[str: list] = {}
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
                modified = stats.st_mtime
                filetype = os.path.splitext(name)[1]

                if self.db_data.get(src):
                    colors = self.db_data.get(src)[0]
                    rating = self.db_data.get(src)[1]
                else:
                    colors = ""
                    rating = 0

            except (PermissionError, FileNotFoundError):
                continue

            # ПОРЯДОК КОРТЕЖА РАВЕН ORDER
            # SRC по которой нет сортировки идет в конце

            if src.lower().endswith(Config.IMG_EXT):
                self.finder_items.append((name, size, modified, filetype, colors, rating, src))
                continue

            if os.path.isdir(src):
                self.finder_items.append((name, size, modified, filetype, colors, rating, src))


class GridStandart(Grid):
    def __init__(self, width: int):
        super().__init__()
        self.ww = width

        # делаем os listdir обход и по сигналу finished
        # запустится создание сетки
        # в конце создания запустится подгрузка изображений
        self.finder_thread = LoadFinder()
        self.finder_thread._finished.connect(self.create_grid)
        self.finder_thread.start()

    def create_grid(self, finder_items: list):
        # (путь, размер, дата): QLabel
        # Для последующей загрузки в LoadImages
        src_size_mod: list[tuple] = []

        col_count = Utils.get_clmn_count(self.ww)
        row, col = 0, 0

        # ПОРЯДОК СООТВЕТСТВУЕТ ORDER + SRC по которому нет сортировки
        for name, size, modify, type, colors, rating, src in finder_items:

            if os.path.isdir(src):
                wid = ThumbFolder(name, src)
                self.set_base_img(wid.img_label, "images/folder_210.png")

                wid.clicked_folder.connect(self.clicked_folder.emit)
                wid.add_fav.connect(self.add_fav.emit)
                wid.del_fav.connect(self.del_fav.emit)

                # у папок нет цветных тегов, но этот метод задает имя
                wid.set_colors("")

            else:
                wid = Thumb(name, size, modify, type, src, self.path_to_wid)
                self.set_base_img(wid.img_label, "images/file_210.png")

                wid.move_to_wid.connect(lambda src: self.move_to_wid(src))
                wid.set_colors(colors)
                wid.set_rating(rating)

                src_size_mod.append((src, size, modify))

            wid.row, wid.col = row, col
            wid.clicked.connect(lambda w=wid: self.select_new_widget(w))
            self.grid_layout.addWidget(wid, row, col)
            self.cell_to_wid[row, col] = wid
            self.path_to_wid[src] = wid

            self.sorted_widgets.append(wid)

            col += 1
            if col >= col_count:
                col = 0
                row += 1

        self.wid_to_cell = {v: k for k, v in self.cell_to_wid.items()}

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

        self.sort_grid(self.ww)

    def set_base_img(self, widget: QLabel, png_path: str):
        pixmap = QPixmap(png_path)
        try:
            widget.setPixmap(pixmap)
        except RuntimeError:
            pass

    def stop_threads(self):
        for i in Threads.all:
            i: LoadImages
            i.stop_thread.emit()

            if i.isFinished():
                Threads.all.remove(i)

    def start_load_images(self, src_size_mod: list[tuple]):
        thread = LoadImages(src_size_mod)
        thread.progressbar_start.connect(self.progressbar_start.emit)
        thread.progressbar_value.connect(self.progressbar_value.emit)
        thread.new_widget.connect(lambda image_data: self.set_pixmap(image_data))
        Threads.all.append(thread)
        thread.start()
    
    def set_pixmap(self, image_data: ImageData):
        widget = self.path_to_wid.get(image_data.src)
        if isinstance(widget, Thumb):
            if isinstance(image_data.pixmap, QPixmap):
                widget.img_label.setPixmap(image_data.pixmap)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        # когда убивается этот виджет, все треды безопасно завершатся
        self.stop_threads()
        return super().closeEvent(a0)