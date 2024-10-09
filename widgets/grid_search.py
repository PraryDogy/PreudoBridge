import os
from ast import literal_eval
from time import sleep

import sqlalchemy
from numpy import ndarray
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QPixmap
from PyQt5.QtWidgets import QAction, QFrame, QSizePolicy, QSpacerItem
import sqlalchemy.exc
import sqlalchemy.orm

from cfg import Config
from database import Cache, Dbase
from fit_img import FitImg
from utils import Utils

from .grid_base import Grid, Thumbnail


# Добавляем в контенкстное меню "Показать в папке"
class _Thumbnail(Thumbnail):
    _show_in_folder = pyqtSignal(str)

    def __init__(self, filename: str, src: str, paths: list):
        super().__init__(filename, src, paths)

        self.context_menu.addSeparator()

        show_in_folder = QAction("Показать в папке", self)
        show_in_folder.triggered.connect(lambda: self._show_in_folder.emit(self.src))
        self.context_menu.addAction(show_in_folder) 


# Тред
# На вход получает директорию для поиска иs текст/шаблон для поиска
# Ищет ТОЛЬКО изображения
# Если найденного изображения нет в БД, то кеширует
# Если есть - загружает изображение кеша
# Отправляется синал _new_widget_sig:
# путь к изображению, os.stat, QPixmap
class _SearchFinderThread(QThread):
    _finished = pyqtSignal()
    _new_widget_sig = pyqtSignal(dict)

    def __init__(self, search_dir: str, search_text: str):
        super().__init__()

        self.search_text: str = search_text
        self.search_dir: str = search_dir
        self.flag: bool = True
        self.session = Dbase.get_session()

    def _stop_cmd(self):
        self.flag: bool = False

    def run(self):
        # Шаблоны в поиске передаются сюда текстовым кортежем, например
        # str( [.jpg, .jpeg] )
        # Мы пытаемся конветировать текст обратно в кортеж
        # Если это кортеж, то поиск производится по шаблону
        # Если это тккст, то по тексту
        # 
        # Шаблоны могут указывать только расширения файлов
        # Можно найти только JPG или все форматы фотографий
        # Шаблон вызывается двойным кликом в поиске
        try:
            self.search_text = literal_eval(self.search_text)
        except (ValueError, SyntaxError):
            pass

        # literal_eval может конвертировать не только кортежи
        # но и числа, а нам нужен только кортеж
        if not isinstance(self.search_text, tuple):
            self.search_text = str(self.search_text)

        self.counter = 0

        for root, _, files in os.walk(self.search_dir):
            if not self.flag:
                break

            for filename in files:
                if not self.flag:
                    break

                src: str = os.path.join(root, filename)
                src_lower: str = src.lower()

                # поиск по шаблону
                if isinstance(self.search_text, tuple):
                    if src_lower.endswith(self.search_text):
                        self._create_wid(src)

                # поиск по тексту
                elif self.search_text in filename and src_lower.endswith(Config.img_ext):
                    self._create_wid(src)

                if self.counter % 10 == 0:
                    Dbase.c_commit(self.session)

                self.counter += 1

        # _finished будет послан только если поиску дали закончить
        # если же он был прерван флагом, то сигнал не будет послан
        # данный сигнал предназначен чтобы сменить заголовок окна с 
        # "поиск файла" на "результаты поиска"
        if self.flag:
            self._finished.emit()

        Dbase.c_commit(self.session)
        self.session.close()

    # общий метод для создания QPixmap, который мы передадим в основной поток
    # для отображения в сетке GridSearch
    def _create_wid(self, src: str):
        try:
            stats = os.stat(src)
        except (PermissionError, FileNotFoundError) as e:
            print("search grid > thread > error get os stat", e)
            return None

        pixmap: QPixmap = None
        db_img: bytes = self._get_db_image(src)

        # Если изображение уже есть в БД, то сразу делаем QPixmap
        if isinstance(db_img, bytes):
            pixmap: QPixmap = Utils.pixmap_from_bytes(db_img)

        # Создаем изображение, ресайзим и записываем в БД
        else:
            new_img: ndarray = self._create_new_image(src)
            self._image_to_db(src, new_img, stats)

            if isinstance(new_img, ndarray):
                pixmap = Utils.pixmap_from_array(new_img)

        # Если не удалось получить изображение, загружаем изображение по умолчанию
        if not pixmap:
            pixmap = QPixmap("images/file_210.png")

        # посылаем сигнал в SearchGrid
        self._new_widget_sig.emit({"src": src, "stats": stats, "pixmap": pixmap})
        sleep(0.2)

    def _get_db_image(self, src: str) -> bytes | None:
        try:
            q = sqlalchemy.select(Cache.img).where(Cache.src==src)
            res = self.session.execute(q).first()
        except sqlalchemy.exc.OperationalError:
            return None

        if isinstance(res, sqlalchemy.engine.Row):
            return res[0]

        return None

    def _image_to_db(self, src: str, img_array, stats: os.stat_result):
        # чтобы несколько раз не запрашивать os.stat
        # мы запрашиваем os.stat в основном цикле os.walk и передаем сюда
        size = stats.st_size
        modified = stats.st_mtime

        # качество по умолчанию 80 для экономии места
        db_img: bytes = Utils.image_array_to_bytes(img_array)

        if isinstance(db_img, bytes):
            q = sqlalchemy.insert(Cache)
            q = q.values({
                "img": db_img,
                "src": src,
                "root": os.path.dirname(src),
                "size": size,
                "modified": modified
                })
            try:
                self.session.execute(q)
            except (sqlalchemy.exc.OperationalError, Exception) as e:
                print("search thread insert db image error: ", e)
                ...

    def _create_new_image(self, src: str) -> ndarray | None:
        img = Utils.read_image(src)
        img = FitImg.start(img, Config.thumb_size)
        return img


# os.walk и чтение изображения происходит в отдельном QThread
# чтобы не блокировать основной интерфейс
# по мере того, как QThread находит и считывает изображение,
# в основной поток посылается сигнал и в сетку добавляется найденное изображение
# 
# во время поиска НЕ работает ресайз и сортировка сетки, поскольку сетка 
# до конца не сформирована
class _GridSearchBase(Grid):
    search_finished = pyqtSignal()

    # для конекстного меню Thumbnail - "показать в папке"
    # программа переходит из поиска в исходную папку с изображением и выделяет его
    show_thumbnail_in_folder = pyqtSignal(str)

    def __init__(self, width: int, search_text: str):
        super().__init__(width)
        self.setAlignment(Qt.AlignmentFlag.AlignTop)

        # (путь до файла, имя файла, размер, дата изменения, тип файла)
        # этот словарик нужен для повторного формирования сетки при изменении
        # размера и для сортировки по имени/размеру/дате/типу
        self._image_grid_widgets: dict[tuple: _Thumbnail] = {}
        self.search_text = search_text

        # row_count наследуется от Grid, поскольку строчки только увеличивают
        # значение при формировании сетки
        # local_col_count это количество колонок, которое сбрасывается при 
        # каждой новой строчке
        self.local_col_count = 0

        clmn_spacer = QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.grid_layout.addItem(clmn_spacer, 0, self.col_count + 1)

        self._thread = _SearchFinderThread(Config.json_data.get("root"), search_text)
        self._thread._new_widget_sig.connect(self._add_new_widget)
        self._thread._finished.connect(self.search_finished.emit)
        self._thread.start()

    def _add_new_widget(self, data: dict):
        # data идет из сигнала _new_widget_sig
        # "src", "stats" - os.stat, "pixmap"
        filename = os.path.basename(data.get("src"))
        wid = _Thumbnail(filename=filename, src=data.get("src"), paths=self._paths)
        wid.img_label.setPixmap(data.get("pixmap"))

        # читай в инициализаторе описание сигнала show_thumbnail_in_folder
        wid._show_in_folder.connect(self.show_thumbnail_in_folder.emit)

        # обычный сигнал по закрытию просмотрщика, читай описание к Grid
        wid._move_to_wid_sig.connect(self._move_to_wid_cmd)

        # любой клик по Thumbnail выделит его и снимет выделение с прошлого
        wid._base_thumb_click.connect(lambda wid=wid: self._clicked_thumb(wid))  

        self.grid_layout.addWidget(wid, self.row_count, self.local_col_count, alignment=Qt.AlignmentFlag.AlignTop)

        ############################################################

        # С помощью данных словарей мы упрощаем навигацию по сетке
        # зображений клавиатурными стрелочками
        # чтобы каждый раз не итерировать и не искать, какой виджет был выделен,
        # а какой нужно выделить теперь

        ############################################################
        self._row_col_wid[self.row_count, self.local_col_count] = wid
        self._wid_row_col[wid] = (self.row_count, self.local_col_count)

        # для метода _move_to_wid
        self._path_widget[data.get("src")] = wid

        # для просмотрщика
        self._paths.append(data.get("src"))

        # прибавляем строчку и столбец в сетку
        self.local_col_count += 1
        if self.local_col_count >= self.col_count:
            self.local_col_count = 0
            self.row_count += 1

        stats: os.stat_result = data.get("stats")
        size = stats.st_size
        modified = stats.st_mtime
        filetype = os.path.splitext(data.get("src"))[1]

        # (путь до файла, имя файла, размер, дата изменения, тип файла)
        # этот словарик нужен для повторного формирования сетки при изменении
        # размера и для сортировки по имени/размеру/дате/типу
        self._image_grid_widgets[(data.get("src"), filename, size, modified, filetype)] = wid

    def _clicked_thumb(self, widget: Thumbnail):
        self._grid_select_widget(QFrame.Shape.NoFrame)
        self._cur_row, self._cur_col = self._wid_row_col.get(widget)
        self._selected_widget = widget
        self._grid_select_widget(QFrame.Shape.Panel)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        try:
            self._thread.disconnect()
        except TypeError:
            pass

        # устанавливаем флаг QThread на False чтобы прервать цикл os.walk
        # происходит session commit и не подается сигнал _finished
        self._thread._stop_cmd()
  

class GridSearch(_GridSearchBase):
    def __init__(self, width: int, search_text: str):
        super().__init__(width, search_text)

    # если поиск еще идет, сетка не переформируется
    # если завершен, то мы формируем новую сетку на основе новых размеров
    def resize_grid(self, width: int):
        if not self._thread.isRunning():

            self._row_col_wid.clear()
            self._wid_row_col.clear()

            self.col_count = Utils.get_clmn_count(width)
            if self.col_count < 1:
                self.col_count = 1

            self.row_count = 0
            self.local_col_count = 0

            # (путь до файла, имя файла, размер, дата изменения, тип файла)
            # этот словарик нужен для повторного формирования сетки при изменении
            # размера и для сортировки по имени/размеру/дате/типу
            for data, wid in self._image_grid_widgets.items():
                self.grid_layout.addWidget(wid, self.row_count, self.local_col_count, alignment=Qt.AlignmentFlag.AlignTop)

                self._row_col_wid[self.row_count, self.local_col_count] = wid
                self._wid_row_col[wid] = (self.row_count, self.local_col_count)

                self.local_col_count += 1
                if self.local_col_count >= self.col_count:
                    self.local_col_count = 0
                    self.row_count += 1
            
            # при итерации виджетов строка прибавляется уже после обработки 
            # виджета, то есть после последнего виджета в последней колонке
            # строка все равно прибавится, они будет лишней, пустой
            # мы проверяем, есть ли на последней строке и первой колонке виджет
            # если нет, значит при итерации выше добавилась лишняя строка
            last_row_check = self._row_col_wid.get((self.row_count, 0))
            if not last_row_check:
                self.row_count -= 1

    # неактивно
    # в идеале нужно для выхода из приложения, потому что только по завершению
    # треда происходит commit сессии, то есть сохраняются в БД все кешированные
    # изображения
    def stop_and_wait_threads(self):
        self._thread._stop_cmd()
        self._thread.session.commit()

    
    def sort_grid(self, width: int):
        sort_data = {"name": 1, "size": 2,  "modify": 3, "type": 4}
        # ключи соответствуют json_data["sort"]
        # значения соответствуют индексам в кортеже у ключей
        # (путь до файла, имя файла, размер, дата изменения, тип файла)
        # начинаем с 1, потому что 0 у нас путь до файла, нам не нужна сортировка по src

        index = sort_data.get(Config.json_data.get("sort"))
        self._image_grid_widgets = dict(
            sorted(self._image_grid_widgets.items(), key=lambda item: item[0][index])
            )

        if Config.json_data["reversed"]:
            self._image_grid_widgets = dict(reversed(self._image_grid_widgets.items()))

        self.resize_grid(width)

    def move_to_wid(self, src: str):
        self._move_to_wid_cmd(src)