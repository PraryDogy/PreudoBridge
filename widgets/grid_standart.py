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
        # копируем словарик из инициатора
        # чтобы защититься во время итерации от случайных изменений
        # почему то вылезала ошибка что словарь изменен во время итерации
        grid_widgets = self.grid_widgets.copy()

        # каждые 10 изображений коммитим в БД
        count = 0

        self._progressbar_start.emit(len(grid_widgets))

        for (src, size, modified), widget in grid_widgets.items():
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
        # копируем словарик из инициатора
        # чтобы защититься во время итерации от случайных изменений
        # почему то вылезала ошибка что словарь изменен во время итерации
        grid_widgets = self.grid_widgets.copy()

        for (src, size, modified), bytearray_image in self.db_images.items():

            # мы сверяем по пути, размеру и дате, есть ли в БД такой же ключ
            key = grid_widgets.get((src, size, modified))

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
        sort_data = {"name": 1, "size": 2,  "modify": 3, "type": 4}
        # начинаем с 1, потому что 0 у нас src, нам не нужна сортировка по src
        # ключи соответствуют json_data["sort"]

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


class _GridStandartBase(Grid):
    add_fav_sig = pyqtSignal(str)
    del_fav_sig = pyqtSignal(str)
    folder_thumb_open_folder_sig = pyqtSignal(str)
    progressbar_start = pyqtSignal(int)
    progressbar_value = pyqtSignal(int)

    def __init__(self, width: int):
        super().__init__(width)

        self._finder_thread = _LoadFinderThread()
        self._finder_thread._finished.connect(self._create_grid)
        self._finder_thread.start()

    def _create_grid(self, _finder_items: dict):
        local_col_count = 0

        # (src, size, modified): QLabel. Для последующей загрузки в _LoadImagesThread
        self._image_grid_widgets: dict[tuple: QPixmap] = {}

        for (src, filename, size, modified, _), _ in _finder_items.items():

            if os.path.isdir(src):
                wid = _FolderThumbnail(filename, src)
                self._set_default_image(wid.img_label, "images/folder_210.png")
                wid._folder_thumb_open_folder_sig.connect(self.folder_thumb_open_folder_sig.emit)
                wid._folder_context_add_fav_sig.connect(self.add_fav_sig.emit)
                wid._foder_context_del_fav_sig.connect(self.del_fav_sig.emit)
                wid._base_thumb_folder_click.connect(self.folder_thumb_open_folder_sig.emit)

            else:
                wid = Thumbnail(filename, src, self._paths)
                wid._move_to_wid_sig.connect(lambda src: self._move_to_wid_cmd(src))
                self._set_default_image(wid.img_label, "images/file_210.png")
                self._image_grid_widgets[(src, size, modified)] = wid.img_label

            wid._base_thumb_click.connect(lambda wid=wid: self._grid_select_new_widget(wid))
            self.grid_layout.addWidget(wid, self.row_count, local_col_count)

            self._row_col_wid[self.row_count, local_col_count] = wid
            self._wid_row_col[wid] = (self.row_count, local_col_count)
            self._path_widget[src] = wid
            if os.path.isfile(src):
                self._paths.append(src)

            local_col_count += 1
            if local_col_count >= self.col_count:
                local_col_count = 0
                self.row_count += 1

        # при итерации виджетов строка прибавляется уже после обработки 
        # виджета, то есть после последнего виджета в последней колонке
        # строка все равно прибавится, они будет лишней, пустой
        # мы проверяем, есть ли на последней строке и первой колонке виджет
        # если нет, значит при итерации выше добавилась лишняя строка
        last_row_check = self._row_col_wid.get((self.row_count, 0))
        if not last_row_check:
            self.row_count -= 1

        if self._row_col_wid:
            row_spacer = QSpacerItem(1, 1, QSizePolicy.Minimum, QSizePolicy.Expanding)
            self.grid_layout.addItem(row_spacer, self.row_count + 1, 0)

            col_spacer = QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum)
            self.grid_layout.addItem(col_spacer, 0, self.col_count + 2)

            self._start_load_images_thread()

        elif not os.path.exists(Config.json_data.get("root")):
            no_images = QLabel(f"{Config.json_data.get('root')}\nТакой папки не существует \n Проверьте подключение к сетевому диску")
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0)

        else:
            no_images = QLabel(f"{Config.json_data.get('root')}\nНет изображений")
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0)

    def _grid_select_new_widget(self, widget: Thumbnail):
        self._grid_select_widget(QFrame.Shape.NoFrame)
        self._cur_row, self._cur_col = self._wid_row_col.get(widget)
        self._selected_widget = widget
        self._grid_select_widget(QFrame.Shape.Panel)

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
        new_thread = _LoadImagesThread(self._image_grid_widgets)
        new_thread._progressbar_start.connect(self.progressbar_start.emit)
        new_thread._progressbar_value.connect(self.progressbar_value.emit)
        new_thread._set_pixmap.connect(self._set_pixmap)
        _Storage.threads.append(new_thread)
        new_thread.start()
    
    def _set_pixmap(self, data: tuple):
        src, size, modified, pixmap = data
        widget: QLabel = self._image_grid_widgets.get((src, size, modified))
        if isinstance(pixmap, QPixmap):
            widget.setPixmap(pixmap)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self._stop_threads()
        return super().closeEvent(a0)
        

class GridStandart(_GridStandartBase):
    def __init__(self, width: int):
        super().__init__(width)

    def resize_grid(self, width: int):
        row_col_widget = self._row_col_wid.copy()
        self._row_col_wid.clear()
        self._wid_row_col.clear()

        self.col_count = Utils.get_clmn_count(width)
        if self.col_count < 1:
            self.col_count = 1

        self.row_count, local_col_count = 0, 0
        self._cur_row, self._cur_col = 0, 0

        for (row, col), wid in row_col_widget.items():

            self.grid_layout.addWidget(wid, self.row_count, local_col_count)

            self._row_col_wid[self.row_count, local_col_count] = wid
            self._wid_row_col[wid] = (self.row_count, local_col_count)

            local_col_count += 1
            if local_col_count >= self.col_count:
                local_col_count = 0
                self.row_count += 1

        # при итерации виджетов строка прибавляется уже после обработки 
        # виджета, то есть после последнего виджета в последней колонке
        # строка все равно прибавится, они будет лишней, пустой
        # мы проверяем, есть ли на последней строке и первой колонке виджет
        # если нет, значит при итерации выше добавилась лишняя строка
        last_row_check = self._row_col_wid.get((self.row_count, 0))
        if not last_row_check:
            self.row_count -= 1

    def stop_and_wait_threads(self):
        for thread in _Storage.threads:
            thread: _LoadImagesThread
            thread._stop_thread.emit()

    def sort_grid(self, width: int):
        self.resize_grid(width)

    def move_to_wid(self, src: str):
        self._move_to_wid_cmd(src)