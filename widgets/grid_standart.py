import os

import numpy as np
import sqlalchemy
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QContextMenuEvent, QMouseEvent, QPixmap
from PyQt5.QtWidgets import QAction, QLabel, QSizePolicy, QSpacerItem
from sqlalchemy.exc import OperationalError

from cfg import Config
from database import CACHE, STATS, Engine
from fit_img import FitImg
from utils import Utils

from .grid_base import Grid, Thumbnail


# Если родительский класс запущенного треда будет закрыт
# Тред получит сигнал стоп и безопасно завершится
class Storage:
    threads: list = []


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

        # копируем, чтобы не менялся родительский словарик
        # потому что на него опирается основной поток
        # а мы удаляем из этого словарика элементы в обходе БД
        # self.stats_pixmap: dict[tuple: QLabel] = stats_pixmap
        self.src_size_mod: list[tuple] = src_size_mod

        # если изображение есть в БД но нет в словарике
        # значит оно было ранее удалено из Findder и будет удалено из БД
        self.remove_db_images: list = []

        # существующие изображения в БД
        self.db_images: dict[tuple: bytearray] = {}
        
        # флаг для остановки, если False - прервется цикл
        self.flag = True
        self.stop_thread.connect(self.stop_thread_cmd)

        # открываем сессию на время треда
        self.conn = Engine.engine.connect()
        self.transaction = self.conn.begin()
        self.insert_count = 0

    def run(self):
        # загружаем изображения по корневой директории из Config.json_data
        self.db_images: dict = self.get_db_images()

        # проверяем какие есть в БД и в словарике, подгружаем в сетку сигналом
        self.load_already_images()

        # остальные изображения создаем, пишем в БД, подружаем в сетку сигналом
        self.create_new_images()

        # удаляем то, чего уже нет в Finder но было в БД
        self.remove_images()

        # последний комит, помимо комитов в цикле
        if self.insert_count > 0:
            self.transaction.commit()
        self.conn.close()

        # не используется
        self._finished.emit()

    def get_db_images(self):
        q = sqlalchemy.select(CACHE.c.img, CACHE.c.src, CACHE.c.size, CACHE.c.modified)
        q = q.where(CACHE.c.root == Config.json_data.get("root"))

        try:
            res = self.conn.execute(q).fetchall()
        except OperationalError:
            return None

        # возвращаем словарик по структуре такой же как входящий
        return {
            (src, size, modified): img
            for img, src, size,  modified in res
            }

    def load_already_images(self):
        for (db_src, db_size, db_mod), db_byte_img in self.db_images.items():

            if not self.flag:
                break

            # если есть в БД, то отправляем изображение в сетку
            # и удаляем из словарика этот элемент
            if (db_src, db_size, db_mod) in self.src_size_mod:
                pixmap: QPixmap = Utils.pixmap_from_bytes(db_byte_img)
                self.new_widget.emit(ImageData(db_src, db_size, db_mod, pixmap))

                # мы удаляем элемент если он есть в базе данных и в Finder
                # в src_size_mod останутся только те элементы
                # которые есть в Finder и нет в БД
                # т.е. то, что это новые Finder элементы, которые 
                # добавятся в БД в последующем методе create_new_images

                self.src_size_mod.remove((db_src, db_size, db_mod))
            else:
                self.remove_db_images.append(db_src)

    def create_new_images(self):
        self.progressbar_start.emit(len(self.src_size_mod))
        count = 0

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

                q = sqlalchemy.insert(CACHE)
                q = q.values(
                    img = img_bytes,
                    src = src,
                    root = Config.json_data.get("root"),
                    size = size,
                    modified = modified,
                    catalog = "",
                    colors = "",
                    stars = ""
                    )
                self.conn.execute(q)

                q = sqlalchemy.select(STATS.c.size).where(STATS.c.name == "main")
                stats_size = self.conn.execute(q).scalar() or 0
                stats_size += len(img_bytes)

                q = sqlalchemy.update(STATS).where(STATS.c.name=="main")
                q = q.values(size = stats_size)
                self.conn.execute(q)

                self.insert_count += 1
                if self.insert_count >= 10:
                    self.transaction.commit()
                    self.transaction = self.conn.begin()
                    self.insert_count = 0

            except (OperationalError ,Exception) as e:
                pass

            self.progressbar_value.emit(count)
            count += 1

        # 1 милилон = скрыть прогресс бар согласно его инструкции
        self.progressbar_value.emit(1000000)

    def remove_images(self):
        for src in self.remove_db_images:
            q = sqlalchemy.delete(CACHE).where(CACHE.c.src == src)
            try:
                self.conn.execute(q)
                self.insert_count += 1
            except OperationalError:
                ...

    def stop_thread_cmd(self):
        self.flag = False


# большие сетевые папки замедляют обход через os listdir
# поэтому мы делаем это в треде
# ищем только изображения и папки в родительской директории Config.json_data
# и добавляем стандартые иконки папок и файлов
# сортируем полученный список соответсвуя Config.json_data
# отправляем в сетку
class LoadFinder(QThread):
    _finished = pyqtSignal(list)

    def __init__(self):
        super().__init__()

    def run(self):
        try:
            db_colors = self.get_db_colors()
            finder_items: list = self.get_items(db_colors)
            finder_items: list = self.sort_items(finder_items)
        except (PermissionError, FileNotFoundError):
            finder_items: list = []
        
        self._finished.emit(finder_items)

    def get_db_colors(self):
        q = sqlalchemy.select(CACHE.c.src, CACHE.c.colors)
        q = q.where(CACHE.c.root == Config.json_data.get("root"))

        with Engine.engine.connect() as conn:
            with conn.begin():
                res = conn.execute(q).fetchall()
                return {src: colors for src, colors in res}

    def get_items(self, db_colors: dict) -> list:
        finder_items = []

        for filename in os.listdir(Config.json_data.get("root")):

            src: str = os.path.join(Config.json_data.get("root"), filename)

            try:
                stats = os.stat(src)
                size = stats.st_size
                modified = stats.st_mtime
                filetype = os.path.splitext(filename)[1]
                colors = db_colors.get(src) or ""
            except (PermissionError, FileNotFoundError):
                continue

            if src.lower().endswith(Config.img_ext):
                finder_items.append((src, filename, size, modified, filetype, colors))
                continue

            elif os.path.isdir(src):
                finder_items.append((src, filename, size, modified, filetype, colors))

        return finder_items
            
    def sort_items(self, finder_items: list):
        # finder_items: src filename size modified filetype
        # мы создаем отдельный словарик, где ключ соответствует Config.json_data "sort"
        # а значение индексу в ключе self.finder_items
        # таким образом если "sort" у нас size, то мы знаем, что нужно сортировать
        # по индексу 2
        sort_data = {"src": 0, "name": 1, "size": 2,  "modify": 3, "type": 4, "colors": 5}
        index = sort_data.get(Config.json_data.get("sort"))
        rev = Config.json_data.get("reversed")

        if index != 5:
            sort_key = lambda x: x[index]
        else:
            sort_key = lambda x: len(x[index])

        return sorted(finder_items, key=sort_key, reverse=rev)


class ThumbnailFolder(Thumbnail):
    add_fav = pyqtSignal(str)
    del_fav = pyqtSignal(str)

    def __init__(self, filename: str, src: str):
        super().__init__(filename, src, [])

        self.context_menu.clear()

        view_action = QAction("Просмотр", self)
        view_action.triggered.connect(lambda: self.clicked_folder.emit(self.src))
        self.context_menu.addAction(view_action)

        self.context_menu.addSeparator()

        show_in_finder_action = QAction("Показать в Finder", self)
        show_in_finder_action.triggered.connect(self._show_in_finder)
        self.context_menu.addAction(show_in_finder_action)

        copy_path = QAction("Скопировать путь до папки", self)
        copy_path.triggered.connect(lambda: Utils.copy_path(self.src))
        self.context_menu.addAction(copy_path)

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

        for src, filename, size, modified, type, colors in finder_items:

            if os.path.isdir(src):
                wid = ThumbnailFolder(filename, src)
                self.set_base_img(wid.img_label, "images/folder_210.png")

                # подключаем сигналы виджеты к сигналу сетки
                wid.clicked_folder.connect(self.clicked_folder.emit)
                wid.add_fav.connect(self.add_fav.emit)
                wid.del_fav.connect(self.del_fav.emit)

            else:
                wid = Thumbnail(filename, src, self.image_paths)
                wid.img_viewer_closed.connect(lambda src: self.move_to_wid(src))
                self.set_base_img(wid.img_label, "images/file_210.png")
                # ADD COLORS TO THUMBNAIL
                wid.update_colors(colors)
                src_size_mod.append((src, size, modified))

            self.grid_layout.addWidget(wid, row, col)
            wid.clicked.connect(lambda r=row, c=col: self.select_new_widget((r, c)))

            # добавляем местоположение виджета в сетке для навигации клавишами
            self.cell_to_wid[row, col] = wid
            self.path_to_wid[src] = wid

            if os.path.isfile(src):
                self.image_paths.append(src)

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
        for i in Storage.threads:
            i: LoadImages
            i.stop_thread.emit()

            if i.isFinished():
                Storage.threads.remove(i)

    def start_load_images(self, src_size_mod: list[tuple]):
        thread = LoadImages(src_size_mod)
        thread.progressbar_start.connect(self.progressbar_start.emit)
        thread.progressbar_value.connect(self.progressbar_value.emit)
        thread.new_widget.connect(lambda image_data: self.set_pixmap(image_data))
        Storage.threads.append(thread)
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
                wid.img_viewer_closed.connect(lambda src: self.move_to_wid(src))

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