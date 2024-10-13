import os

import numpy as np
import sqlalchemy
import sqlalchemy.exc
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QContextMenuEvent, QKeyEvent, QMouseEvent, QPixmap
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
            img = FitImg.start(img, Config.img_size)

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
                    "modified": modified,
                    "catalog": "",
                    "colors": "",
                    "stars": ""
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
        self.db_colors: dict[str: str] = {}

    def run(self):
        try:
            self.get_db_colors()
            self._get_items()
            self._sort_items()
        except (PermissionError, FileNotFoundError):
            self.finder_items: dict[tuple: None] = {}
        
        self._finished.emit(self.finder_items)

    def get_db_colors(self):
        sess = Dbase.get_session()
        q = sqlalchemy.select(Cache.src, Cache.colors)
        q = q.where(Cache.root == Config.json_data.get("root"))
        res = sess.execute(q).fetchall()

        self.db_colors = {src: colors for src, colors in res}

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
            colors = self.db_colors.get(src)

            if not isinstance(colors, str):
                colors = ""

            if src.lower().endswith(Config.img_ext):
                self.finder_items[(src, filename, size, modified, filetype, colors)] = None
                continue

            elif os.path.isdir(src):
                self.finder_items[(src, filename, size, modified, filetype, colors)] = None
            
    def _sort_items(self):
        # finder_items: src filename size modified filetype
        # мы создаем отдельный словарик, где ключ соответствует Config.json_data "sort"
        # а значение индексу в ключе self.finder_items
        # таким образом если "sort" у нас size, то мы знаем, что нужно сортировать
        # по индексу 2
        sort_data = {"src": 0, "name": 1, "size": 2,  "modify": 3, "type": 4, "colors": 5}

        index = sort_data.get(Config.json_data.get("sort"))
            
        if index < 5:
            sort_key = lambda item: item[0][index]
        else:
            sort_key = lambda item: len(item[0][index])

        self.finder_items = dict(sorted(self.finder_items.items(), key=sort_key))     

        if Config.json_data["reversed"]:
            self.finder_items = dict(reversed(self.finder_items.items()))


class _FolderThumbnail(Thumbnail):
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

    # def view(self):
        # self.clicked.emit()
        # self.clicked_folder.emit(self.src)

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
class _GridStandartBase(Grid):
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
        self._finder_thread = _LoadFinderThread()
        self._finder_thread._finished.connect(self._create_grid)
        self._finder_thread.start()

    def _create_grid(self, _finder_items: dict):
        # (путь, размео, дата): QLabel
        # Для последующей загрузки в _LoadImagesThread
        self._load_images_data: dict[tuple: QPixmap] = {}

        col_count = Utils.get_clmn_count(self.ww)
        row, col = 0, 0

        for (src, filename, size, modified, _, colors), _ in _finder_items.items():

            if os.path.isdir(src):
                wid = _FolderThumbnail(filename, src)
                self._set_default_image(wid.img_label, "images/folder_210.png")

                # подключаем сигналы виджеты к сигналу сетки
                wid.clicked_folder.connect(self.clicked_folder.emit)
                wid.add_fav.connect(self.add_fav.emit)
                wid.del_fav.connect(self.del_fav.emit)

            else:
                wid = Thumbnail(filename, src, self._paths_images)
                wid.img_viewer_closed.connect(lambda src: self.move_to_wid(src))
                self._set_default_image(wid.img_label, "images/file_210.png")
                # ADD COLORS TO THUMBNAIL
                wid.update_colors(colors)
                # добавляем в словарик для подгрузки изображений
                self._load_images_data[(src, size, modified)] = wid.img_label

            self.grid_layout.addWidget(wid, row, col)
            wid.clicked.connect(lambda r=row, c=col: self.select_new_widget((r, c)))

            # добавляем местоположение виджета в сетке для навигации клавишами
            self.coords[row, col] = wid
            self._paths_widgets[src] = wid

            if os.path.isfile(src):
                self._paths_images.append(src)

            col += 1
            if col >= col_count:
                col = 0
                row += 1

        self.coords_reversed = {v: k for k, v in self.coords.items()}

        if self.coords:
            row_spacer = QSpacerItem(1, 1, QSizePolicy.Minimum, QSizePolicy.Expanding)
            self.grid_layout.addItem(row_spacer, row + 2, 0)

            col_spacer = QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum)
            self.grid_layout.addItem(col_spacer, 0, col_count + 2)

            self._start_load_images_thread()

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
        widget = self._paths_widgets.get(src)

        if isinstance(widget, Thumbnail):

            if isinstance(pixmap, QPixmap):
                widget.img_label.setPixmap(pixmap)

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

            if isinstance(wid, _FolderThumbnail):
                wid.disconnect()
                wid.clicked_folder.connect(self.clicked_folder.emit)
                wid.add_fav.connect(self.add_fav.emit)
                wid.del_fav.connect(self.del_fav.emit)
        
            elif isinstance(wid, Thumbnail):
                wid.disconnect()
                wid.img_viewer_closed.connect(lambda src: self.move_to_wid(src))

            wid.clicked.connect(lambda r=row, c=col: self.select_new_widget((r, c)))
            self.grid_layout.addWidget(wid, row, col)
            self.coords[row, col] = wid

            col += 1
            if col >= col_count:
                col = 0
                row += 1

        self.coords_reversed = {v: k for k, v in self.coords.items()}

    # ссылка на внутренний метод для полиморфности
    # нужно для функции "перейти" которая открывает путь к файлу
    # чтобы выделить искомый файл в сетке
    # и для выделения файла после закрытия просмотрщика изображений 
    def move_to_wid(self, src: str):
        self.move_to_wid(src)