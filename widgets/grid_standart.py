import os

import numpy as np
import sqlalchemy
import sqlalchemy.exc
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QContextMenuEvent, QMouseEvent, QPixmap
from PyQt5.QtWidgets import QAction, QFrame, QLabel, QSizePolicy, QSpacerItem

from cfg import Config
from database import Cache, Dbase
from fit_img import FitImg
from utils import Utils

from .grid_base import Grid, Thumbnail

# Если родительский класс запущенного треда будет закрыт
# Тред получит сигнал стоп и безопасно завершится
class _Storage:
    threads: list = []

# Данный тред получает на вхол словарик {(путь, размер, дата): виджет для Pixmap}
# по ключам ищем существующие изображения в БД
# если есть - подгружаем в сетку
# если нет - считываем, делаем запись в БД, подгружаем в сетку
class _LoadImagesThread(QThread):

    # передает обратно (путь, размер, дата): PIXMAP
    # чтобы в основном потоке в словарике найти виджет и применить изображение
    _set_pixmap = pyqtSignal(tuple)

    # отправляем в основное приложение чтобы показать прогресс
    _progressbar_start = pyqtSignal(int)
    _progressbar_value = pyqtSignal(int)

    # флаг проверяется в цикле и если False то цикл прерывается
    _stop_thread = pyqtSignal()

    # не используется
    _finished = pyqtSignal()
    
    def __init__(self, grid_widgets: dict[tuple: QLabel]):
        super().__init__()

        # копируем, чтобы не менялся родительский словарик
        # потому что на него опирается основной поток
        # а мы удаляем из этого словарика элементы в обходе БД
        self.grid_widgets: dict[tuple: QLabel] = grid_widgets.copy()

        # если изображение есть в БД но нет в словарике
        # значит оно было ранее удалено из Findder и будет удалено из БД
        self.remove_db_images: dict[tuple: None] = {}

        # существующие изображения в БД
        self.db_images: dict = {}
        
        # флаг для остановки, если False - прервется цикл
        self.flag = True
        self._stop_thread.connect(self._stop_thread_cmd)

        # открываем сессию на время треда
        self.session = Dbase.get_session()

    def run(self):
        # загружаем изображения по корневой директории из Config.json_data
        self.db_images: dict = self._get_db_images()

        # проверяем какие есть в БД и в словарике, подгружаем в сетку сигналом
        self._load_already_images()

        # остальные изображения создаем, пишем в БД, подружаем в сетку сигналом
        self._create_new_images()

        # удаляем то, чего уже нет в Finder но было в БД
        self._remove_images()

        # последний комит, помимо комитов в цикле
        Dbase.c_commit(self.session)
        self.session.close()

        # не используется
        self._finished.emit()

    def _create_new_images(self):
        # каждые 10 изображений коммитим в БД
        count = 0

        self._progressbar_start.emit(len(self.grid_widgets))

        for (src, size, modified), widget in self.grid_widgets.items():
            if not self.flag:
                break

            if os.path.isdir(src):
                continue

            if count % 10 == 0:
                Dbase.c_commit(self.session)

            img = Utils.read_image(src)
            img = FitImg.start(img, Config.thumb_size)

            try:
                # numpy array в PIXMAP и сигнал в сетку
                self._set_new_image((src, size, modified), img)
            except AttributeError as e:
                pass

            try:
                # numpy array в БД
                img = Utils.image_array_to_bytes(img)

                if not isinstance(img, bytes):
                    continue

                q = sqlalchemy.insert(Cache)
                q = q.values({
                    "img": img,
                    "src": src,
                    "root": Config.json_data.get("root"),
                    "size": size,
                    "modified": modified
                    })
                self.session.execute(q)
            except (sqlalchemy.exc.OperationalError ,Exception) as e:
                pass

            self._progressbar_value.emit(count)
            count += 1

        # 1 милилон = скрыть прогресс бар согласно его инструкции
        self._progressbar_value.emit(1000000)

    def _load_already_images(self):
        for (src, size, modified), bytearray_image in self.db_images.items():

            # мы сверяем по пути, размеру и дате, есть ли в БД такой же ключ
            key = self.grid_widgets.get((src, size, modified))

            if not self.flag:
                break

            # если есть в БД, то отправляем изображение в сетку
            # и удаляем из словарика этот элемент
            if key:
                pixmap: QPixmap = Utils.pixmap_from_bytes(bytearray_image)
                self._set_pixmap.emit((src, size, modified, pixmap))

                # !!! очень важный момент
                # потому что следом за проверкой БД изображений
                # последует обход ОСТАВШИХСЯ в self.grid_widgets элементов
                # то есть после этой итерации с БД в словаре останутся
                # только НОВЫЕ изображения, которые вставим в БД и сетку
                self.grid_widgets.pop((src, size, modified))
            else:
                self.remove_db_images[(src, size, modified)] = None

    def _remove_images(self):
        for (src, _, _), _ in self.remove_db_images.items():
            q = sqlalchemy.delete(Cache)
            q = q.where(Cache.src==src)
            try:
                self.session.execute(q)
            except sqlalchemy.exc.OperationalError:
                ...

    def _get_db_images(self):
        q = sqlalchemy.select(Cache.img, Cache.src, Cache.size, Cache.modified)
        q = q.where(Cache.root==Config.json_data.get("root"))

        try:
            res = self.session.execute(q).fetchall()
        except sqlalchemy.exc.OperationalError:
            return None

        # возвращаем словарик по структуре такой же как входящий
        return {
            (src, size, modified): img
            for img, src, size,  modified in res
            }

    def _stop_thread_cmd(self):
        self.flag = False

    def _set_new_image(self, data: tuple, image: np.ndarray):
        pixmap = Utils.pixmap_from_array(image)
        try:
            src, size, modified = data
            self._set_pixmap.emit((src, size, modified, pixmap))
        except RuntimeError:
            pass


# большие сетевые папки замедляют обход через os listdir
# поэтому мы делаем это в треде
# ищем только изображения и папки в родительской директории Config.json_data
# и добавляем стандартые иконки папок и файлов
# сортируем полученный список соответсвуя Config.json_data
# отправляем в сетку
class _LoadFinderThread(QThread):
    _finished = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.finder_items: dict[tuple: None] = {}

    def run(self):
        try:
            self._get_items()
            self._sort_items()
        except (PermissionError, FileNotFoundError):
            self.finder_items: dict[tuple: None] = {}
        
        self._finished.emit(self.finder_items)

    def _get_items(self):
        for filename in os.listdir(Config.json_data.get("root")):
            src: str = os.path.join(Config.json_data.get("root"), filename)

            try:
                stats = os.stat(src)
            except (PermissionError, FileNotFoundError):
                continue

            size = stats.st_size
            modified = stats.st_mtime
            filetype = os.path.splitext(filename)[1]

            if src.lower().endswith(Config.img_ext):
                self.finder_items[(src, filename, size, modified, filetype)] = None
                continue

            elif os.path.isdir(src):
                self.finder_items[(src, filename, size, modified, filetype)] = None
            
    def _sort_items(self):
        # ключ finder_items src filename size modified filetype
        # а мы осуществляем сортировку только filename size modified filetype
        # поэтому мы создаем отдельный словарик, где
        # имя соответствует Config.json_data "sort"
        # а значение индексу в ключе self.finder_items
        # таким образом если "sort" у нас size, то мы знаем, что нужно сортировать
        # по индексу 2
        sort_data = {"name": 1, "size": 2,  "modify": 3, "type": 4}

        index = sort_data.get(Config.json_data.get("sort"))
        self.finder_items = dict(
            sorted(self.finder_items.items(), key=lambda item: item[0][index])
            )

        if Config.json_data["reversed"]:
            self.finder_items = dict(reversed(self.finder_items.items()))


class _FolderThumbnail(Thumbnail):
    _folder_context_add_fav_sig = pyqtSignal(str)
    _foder_context_del_fav_sig = pyqtSignal(str)
    _folder_thumb_open_folder_sig = pyqtSignal(str)

    def __init__(self, filename: str, src: str):
        super().__init__(filename, src, [])

        self.context_menu.clear()

        view_action = QAction("Просмотр", self)
        view_action.triggered.connect(lambda: self._folder_thumb_open_folder_sig.emit(self.src))
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
            self.fav_action.triggered.connect(lambda: self._fav_cmd(-1))
            self.context_menu.addAction(self.fav_action)
        else:
            self.fav_action = QAction("Добавить в избранное", self)
            self.fav_action.triggered.connect(lambda: self._fav_cmd(+1))
            self.context_menu.addAction(self.fav_action)

    def mouseDoubleClickEvent(self, a0: QMouseEvent | None) -> None:
        # это FOLDER THUMB, поэтому мы переопределяем double click
        # отправляем сигнал в сетку чтобы выделить этот виджет
        self._base_thumb_click.emit()

        # отправляем сигнал в сетку чтобы открыть папку
        self._folder_thumb_open_folder_sig.emit(self.src)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        self._base_thumb_click.emit()
        self.context_menu.exec_(self.mapToGlobal(a0.pos()))

    def _fav_cmd(self, offset: int):
        self.fav_action.triggered.disconnect()
        if 0 + offset == 1:
            self._folder_context_add_fav_sig.emit(self.src)
            self.fav_action.setText("Удалить из избранного")
            self.fav_action.triggered.connect(lambda: self._fav_cmd(-1))
        else:
            self._foder_context_del_fav_sig.emit(self.src)
            self.fav_action.setText("Добавить в избранное")
            self.fav_action.triggered.connect(lambda: self._fav_cmd(+1))


# Базовый класс со внутренними методами не для импорта
class _GridStandartBase(Grid):
    # сигналы переданные из FOLDER THUMBNAIL
    add_fav_sig = pyqtSignal(str)
    del_fav_sig = pyqtSignal(str)
    folder_thumb_open_folder_sig = pyqtSignal(str)

    # сигналы из треда по загрузке изображений
    progressbar_start = pyqtSignal(int)
    progressbar_value = pyqtSignal(int)

    def __init__(self, width: int):
        super().__init__(width)
        self.ww = width

        # делаем os listdir обход и по сигналу finished
        # запустится создание сетки
        # в конце создания запустится подгрузка изображений
        self._finder_thread = _LoadFinderThread()
        self._finder_thread._finished.connect(self._create_grid)
        self._finder_thread.start()

    def _create_grid(self, _finder_items: dict):

        # ROW COUNT сейчас так же равен 0 при инициации BASE GRID
        # COL COUNT узнает количество колонок при инициации BASE GRID

        # local coint нужен для итерации
        # local_col_count = 0

        # (путь, размео, дата): QLabel
        # Для последующей загрузки в _LoadImagesThread
        self._load_images_data: dict[tuple: QPixmap] = {}

        col_count = Utils.get_clmn_count(self.ww)
        row, col = 0, 0

        for (src, filename, size, modified, _), _ in _finder_items.items():

            if os.path.isdir(src):
                wid = _FolderThumbnail(filename, src)
                self._set_default_image(wid.img_label, "images/folder_210.png")

                # подключаем сигналы виджеты к сигналу сетки
                wid._folder_thumb_open_folder_sig.connect(self.folder_thumb_open_folder_sig.emit)
                wid._folder_context_add_fav_sig.connect(self.add_fav_sig.emit)
                wid._foder_context_del_fav_sig.connect(self.del_fav_sig.emit)
                wid._base_thumb_folder_click.connect(self.folder_thumb_open_folder_sig.emit)

            else:
                wid = Thumbnail(filename, src, self._paths_images)
                wid._move_to_wid_sig.connect(lambda src: self._move_to_wid_cmd(src))
                self._set_default_image(wid.img_label, "images/file_210.png")

                # добавляем в словарик для подгрузки изображений
                self._load_images_data[(src, size, modified)] = wid.img_label

            self.grid_layout.addWidget(wid, row, col)
            wid._base_thumb_click.connect(lambda r=row, c=col: self.select_new_widget((r, c)))

            # добавляем местоположение виджета в сетке для навигации клавишами
            self.coords[row, col] = wid

            # для поиска виджета по пути к файлу
            # это нужно когда закрывается просмотрщик изображений
            # который сигналом возвращает, на каком изображении остановился просмотр
            # чтобы выделить этот виджет в сетке
            self._paths_widgets[src] = wid
            if os.path.isfile(src):
                self._paths_images.append(src)

            col += 1
            if col >= col_count:
                col = 0
                row += 1

        self.coords_reversed = {v: k for k, v in self.coords.items()}

        # добавляем спейсеры чтобы сетка была слева сверху
        if self.coords:
            row_spacer = QSpacerItem(1, 1, QSizePolicy.Minimum, QSizePolicy.Expanding)
            self.grid_layout.addItem(row_spacer, row + 1, 0)

            col_spacer = QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum)
            self.grid_layout.addItem(col_spacer, 0, col_count + 1)

            self._start_load_images_thread()

        # если же словарик пустой значит либо нет папок и фото
        # либо директория не существует
        # такое бывает если в закладках TREE FAVORITES есть директория
        # которой уже не существует
        # или же программа впервые загружается на несуществующей директории
        elif not os.path.exists(Config.json_data.get("root")):
            no_images = QLabel(f"{Config.json_data.get('root')}\nТакой папки не существует \n Проверьте подключение к сетевому диску")
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0)

        # нет фото
        else:
            no_images = QLabel(f"{Config.json_data.get('root')}\nНет изображений")
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0)

    def _set_default_image(self, widget: QLabel, png_path: str):
        pixmap = QPixmap(png_path)
        try:
            widget.setPixmap(pixmap)
        except RuntimeError:
            pass

    def _stop_threads(self):
        for i in _Storage.threads:
            i: _LoadImagesThread
            i._stop_thread.emit()

            if i.isFinished():
                _Storage.threads.remove(i)

    def _start_load_images_thread(self):
        new_thread = _LoadImagesThread(self._load_images_data)
        new_thread._progressbar_start.connect(self.progressbar_start.emit)
        new_thread._progressbar_value.connect(self.progressbar_value.emit)
        new_thread._set_pixmap.connect(self._set_pixmap)
        _Storage.threads.append(new_thread)
        new_thread.start()
    
    def _set_pixmap(self, data: tuple):
        src, size, modified, pixmap = data
        widget: QLabel = self._load_images_data.get((src, size, modified))
        if isinstance(pixmap, QPixmap):
            widget.setPixmap(pixmap)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        # когда убивается этот виджет, все треды безопасно завершатся
        self._stop_threads()
        return super().closeEvent(a0)
        

class GridStandart(_GridStandartBase):
    def __init__(self, width: int):
        super().__init__(width)

    # метод вызывается если была изменена сортировка или размер окна
    # тогда нет необходимости заново делать обход в Finder и грузить изображения
    # здесь только пересортируется сетка
    def resize_grid(self, width: int):

        # копируем для итерации виджетов
        # нам нужны только значения ключей, там записаны виджеты
        coords = self.coords.copy()

        # очищаем для нового наполнения
        self.coords.clear()
        self.coords_reversed.clear()
        self.coords_cur = (0, 0)

        # получаем новое количество колонок на случай изменения размера окна
        col_count = Utils.get_clmn_count(width)
        row, col = 0, 0

        for (_row, _col), wid in coords.items():
            self.grid_layout.addWidget(wid, row, col)

            wid: Thumbnail
            wid.disconnect()
            wid._base_thumb_click.connect(lambda r=row, c=col: self.select_new_widget((r, c)))

            self.coords[row, col] = wid

            col += 1
            if col >= col_count:
                col = 0
                row += 1

        self.coords_reversed = {v: k for k, v in self.coords.items()}

    def stop_and_wait_threads(self):
        for thread in _Storage.threads:
            thread: _LoadImagesThread
            thread._stop_thread.emit()

    # это заглушка для полиморфности
    # чтобы сортировать сетку, GRID инициируется заново в приложении
    def sort_grid(self, width: int):
        self.resize_grid(width)

    # ссылка на внутренний метод для полиморфности
    # нужно для функции "перейти" которая открывает путь к файлу
    # чтобы выделить искомый файл в сетке
    # и для выделения файла после закрытия просмотрщика изображений 
    def move_to_wid(self, src: str):
        self._move_to_wid_cmd(src)