import os

import sqlalchemy
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QContextMenuEvent, QMouseEvent, QPixmap
from PyQt5.QtWidgets import QAction, QLabel, QSizePolicy, QSpacerItem
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import Config
from database import CACHE, STATS, Engine
from fit_img import FitImg
from utils import Utils

from .grid_base import Grid, Thumbnail


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
        q = q.where(CACHE.c.root == Config.json_data.get("root"))
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
            img_array = FitImg.start(img_array, Config.img_size)
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
            self.sort_items()
        except (PermissionError, FileNotFoundError) as e:
            Utils.print_error(self, e)
            self.finder_items: list = []
        
        self._finished.emit(self.finder_items)

    def get_db_data(self):
        q = sqlalchemy.select(CACHE.c.src, CACHE.c.colors, CACHE.c.rating)
        q = q.where(CACHE.c.root == Config.json_data.get("root"))
  
        with Engine.engine.connect() as conn:
            res = conn.execute(q).fetchall()
            self.db_data = {src: [colors, rating] for src, colors, rating in res}

    def get_items(self) -> list:
        for filename in os.listdir(Config.json_data.get("root")):

            src: str = os.path.join(Config.json_data.get("root"), filename)

            try:
                stats = os.stat(src)
                size = stats.st_size
                modified = stats.st_mtime
                filetype = os.path.splitext(filename)[1]

                if self.db_data.get(src):
                    colors = self.db_data.get(src)[0]
                    rating = self.db_data.get(src)[1]
                else:
                    colors = ""
                    rating = 0

            except (PermissionError, FileNotFoundError):
                continue

            if src.lower().endswith(Config.img_ext):
                self.finder_items.append((src, filename, size, modified, filetype, colors, rating))
                continue

            if os.path.isdir(src):
                self.finder_items.append((src, filename, size, modified, filetype, colors, rating))
            
    def sort_items(self):
        # finder_items: src filename size modified filetype colors rating
        # мы создаем словарик, где ключ соответствует Config.json_data "sort"
        # а значение индексу в ключе self.finder_items
        # например
        # таким образом если "sort" у нас size, то мы знаем, что нужно сортировать
        # по индексу 2
        sort_data = {
            "src": 0,
            "name": 1,
            "size": 2,
            "modify": 3,
            "type": 4,
            "colors": 5,
            "rating": 6
            }
        index = sort_data.get(Config.json_data.get("sort"))
        rev = Config.json_data.get("reversed")

        if index != 5:
            sort_key = lambda x: x[index]
        else:
            sort_key = lambda x: len(x[index])

        self.finder_items = sorted(self.finder_items, key=sort_key, reverse=rev)


class ThumbnailFolder(Thumbnail):
    add_fav = pyqtSignal(str)
    del_fav = pyqtSignal(str)

    def __init__(self, filename: str, src: str):
        super().__init__(filename, src, {})

        self.context_menu.clear()

        view_action = QAction("Просмотр", self)
        view_action.triggered.connect(lambda: self.clicked_folder.emit(self.src))
        self.context_menu.addAction(view_action)

        self.context_menu.addSeparator()

        show_in_finder_action = QAction("Показать в Finder", self)
        show_in_finder_action.triggered.connect(self.show_in_finder)
        self.context_menu.addAction(show_in_finder_action)

        copy_path = QAction("Скопировать путь до папки", self)
        copy_path.triggered.connect(lambda: Utils.copy_path(self.src))
        self.context_menu.addAction(copy_path)

        rename = QAction("Переименовать", self)
        rename.triggered.connect(self.rename_win)
        self.context_menu.addAction(rename)

        self.context_menu.addSeparator()

        if self.src in Config.json_data["favs"]:
            self.fav_action = QAction("Удалить из избранного", self)
            self.fav_action.triggered.connect(lambda: self.fav_cmd(-1))
            self.context_menu.addAction(self.fav_action)
        else:
            self.fav_action = QAction("Добавить в избранное", self)
            self.fav_action.triggered.connect(lambda: self.fav_cmd(+1))
            self.context_menu.addAction(self.fav_action)

    def mouseDoubleClickEvent(self, a0: QMouseEvent | None) -> None:
        self.clicked.emit()
        self.clicked_folder.emit(self.src)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        self.clicked.emit()
        self.context_menu.exec_(self.mapToGlobal(a0.pos()))

    def fav_cmd(self, offset: int):
        self.fav_action.triggered.disconnect()
        if 0 + offset == 1:
            self.add_fav.emit(self.src)
            self.fav_action.setText("Удалить из избранного")
            self.fav_action.triggered.connect(lambda: self.fav_cmd(-1))
        else:
            self.del_fav.emit(self.src)
            self.fav_action.setText("Добавить в избранное")
            self.fav_action.triggered.connect(lambda: self.fav_cmd(+1))


# Базовый класс со внутренними методами не для импорта
class GridStandart(Grid):
    # сигналы переданные из FOLDER THUMBNAIL
    add_fav = pyqtSignal(str)
    del_fav = pyqtSignal(str)
    clicked_folder = pyqtSignal(str)

    # сигналы из треда по загрузке изображений
    progressbar_start = pyqtSignal(int)
    progressbar_value = pyqtSignal(int)

    def __init__(self, width: int):
        super().__init__(width)
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

        for src, filename, size, modified, type, colors, rating in finder_items:

            if os.path.isdir(src):
                wid = ThumbnailFolder(filename, src)
                self.set_base_img(wid.img_label, "images/folder_210.png")

                # подключаем сигналы виджеты к сигналу сетки
                wid.clicked_folder.connect(self.clicked_folder.emit)
                wid.add_fav.connect(self.add_fav.emit)
                wid.del_fav.connect(self.del_fav.emit)

                # у папок нет цветных тегов, но этот метод задает имя
                wid.set_colors("")

            else:
                wid = Thumbnail(filename, src, self.path_to_wid)
                wid.move_to_wid.connect(lambda src: self.move_to_wid(src))
                self.set_base_img(wid.img_label, "images/file_210.png")
                # ADD COLORS TO THUMBNAIL
                wid.set_colors(colors)
                wid.set_rating(rating)
                src_size_mod.append((src, size, modified))

            self.grid_layout.addWidget(wid, row, col)
            wid.clicked.connect(lambda r=row, c=col: self.select_new_widget((r, c)))

            # добавляем местоположение виджета в сетке для навигации клавишами
            self.cell_to_wid[row, col] = wid
            self.path_to_wid[src] = wid

            col += 1
            if col >= col_count:
                col = 0
                row += 1

        self.wid_to_cell = {v: k for k, v in self.cell_to_wid.items()}

        if self.cell_to_wid:
            row_spacer = QSpacerItem(1, 1, QSizePolicy.Minimum, QSizePolicy.Expanding)
            self.grid_layout.addItem(row_spacer, row + 2, 0)

            col_spacer = QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum)
            self.grid_layout.addItem(col_spacer, 0, col_count + 2)

            self.start_load_images(src_size_mod)

        elif not os.path.exists(Config.json_data.get("root")):
            t = f"{Config.json_data.get('root')}\nТакой папки не существует\nПроверьте подключение к сетевому диску"
            setattr(self, "no_images", t)

        else:
            t = f"{Config.json_data.get('root')}\nНет изображений"
            if Config.color_filters:
                t = f"{t} с фильтрами: {''.join(Config.color_filters)}"
            if Config.rating_filter > 0:
                stars = '\U00002605' * Config.rating_filter
                t = f"{t}\nС рейтингом: {stars}"
            setattr(self, "no_images", t)

        if hasattr(self, "no_images"):
            no_images = QLabel(t)
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0)

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

        if isinstance(widget, Thumbnail):

            if isinstance(image_data.pixmap, QPixmap):
                widget.img_label.setPixmap(image_data.pixmap)

    # метод вызывается если была изменена сортировка или размер окна
    # тогда нет необходимости заново делать обход в Finder и грузить изображения
    # здесь только пересортируется сетка
    def resize_grid(self, width: int):

        # копируем для итерации виджетов
        # нам нужны только значения ключей, там записаны виджеты
        coords = self.cell_to_wid.copy()

        # очищаем для нового наполнения
        self.cell_to_wid.clear()
        self.wid_to_cell.clear()
        self.curr_cell = (0, 0)

        # получаем новое количество колонок на случай изменения размера окна
        col_count = Utils.get_clmn_count(width)
        row, col = 0, 0

        for (_row, _col), wid in coords.items():

            if isinstance(wid, ThumbnailFolder):
                wid.disconnect()
                wid.clicked_folder.connect(self.clicked_folder.emit)
                wid.add_fav.connect(self.add_fav.emit)
                wid.del_fav.connect(self.del_fav.emit)
        
            elif isinstance(wid, Thumbnail):
                wid.disconnect()
                wid.move_to_wid.connect(lambda src: self.move_to_wid(src))

            wid.clicked.connect(lambda r=row, c=col: self.select_new_widget((r, c)))
            self.grid_layout.addWidget(wid, row, col)
            self.cell_to_wid[row, col] = wid

            col += 1
            if col >= col_count:
                col = 0
                row += 1

        self.wid_to_cell = {v: k for k, v in self.cell_to_wid.items()}

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        # когда убивается этот виджет, все треды безопасно завершатся
        self.stop_threads()
        return super().closeEvent(a0)