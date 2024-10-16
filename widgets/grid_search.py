import os
from ast import literal_eval
from time import sleep

import sqlalchemy
from numpy import ndarray
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QPixmap
from PyQt5.QtWidgets import QAction, QSizePolicy, QSpacerItem
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import Config
from database import CACHE, STATS, Engine
from fit_img import FitImg
from utils import Utils

from .grid_base import Grid, Thumbnail


class ThumbnailSearch(Thumbnail):
    show_in_folder = pyqtSignal(str)

    def __init__(self, filename: str, src: str, path_to_wid: dict[str: Thumbnail]):
        super().__init__(filename, src, path_to_wid)

        self.context_menu.addSeparator()

        show_in_folder = QAction("Показать в папке", self)
        show_in_folder.triggered.connect(lambda: self.show_in_folder.emit(self.src))
        self.context_menu.addAction(show_in_folder) 


class WidgetData:
    def __init__(self, src: str, colors: str, stats: os.stat_result, pixmap: QPixmap):
        self.src: str = src
        self.colors: str = colors
        self.stats: os.stat_result = stats
        self.pixmap: QPixmap = pixmap


class SearchFinder(QThread):
    _finished = pyqtSignal()
    add_new_widget = pyqtSignal(WidgetData)

    def __init__(self, search_text: str):
        super().__init__()

        self.search_text: str = search_text
        self.flag: bool = True

        self.conn: sqlalchemy.Connection = Engine.engine.connect()
        self.insert_count: int = 0 

    def _stop_cmd(self):
        self.flag: bool = False

    def run(self):
        try:
            self.search_text: tuple = literal_eval(self.search_text)
        except (ValueError, SyntaxError):
            pass

        if not isinstance(self.search_text, tuple):
            self.search_text: str = str(self.search_text)

        for root, _, files in os.walk(Config.json_data.get("root")):
            if not self.flag:
                break

            for file in files:
                if not self.flag:
                    break

                file_path: str = os.path.join(root, file)
                file_path_lower: str = file_path.lower()

                if file_path_lower.endswith(self.search_text):

                    # поиск по шаблону
                    if isinstance(self.search_text, tuple):
                        self.create_wid(file_path)

                    # поиск по тексту
                    elif self.search_text in file:
                        self.create_wid(file_path)

        if self.insert_count > 0:
            try:
                self.conn.commit()
            except (IntegrityError, OperationalError) as e:
                Utils.print_error(self, e)

        self.conn.close()

        if self.flag:
            self._finished.emit()

    def create_wid(self, src: str):
        try:
            stats = os.stat(src)
        except (PermissionError, FileNotFoundError) as e:
            Utils.print_error(self, e)
            return None

        pixmap: QPixmap = None
        colors: str = ""

        db_data: dict = self.get_img_data_db(src)

        if isinstance(db_data, dict):
            pixmap: QPixmap = Utils.pixmap_from_bytes(db_data.get("img"))
            colors = db_data.get("colors")

        else:
            img_array: ndarray = self.create_img_array(src)
            self.img_data_to_db(src, img_array, stats)

            if isinstance(img_array, ndarray):
                pixmap = Utils.pixmap_from_array(img_array)

        if not pixmap:
            pixmap = QPixmap("images/file_210.png")

        self.add_new_widget.emit(WidgetData(src, colors, stats, pixmap))
        sleep(0.1)

    def get_img_data_db(self, src: str) -> dict | None:
        try:
            sel_stmt = sqlalchemy.select(CACHE.c.img, CACHE.c.colors).where(CACHE.c.src == src)
            res = self.conn.execute(sel_stmt).first()

            if res:
                return {"img": res.img, "colors": res.colors}
            else:
                return None

        except OperationalError:
            return None

    def img_data_to_db(self, src: str, img_array, stats: os.stat_result):
        size = stats.st_size
        modified = stats.st_mtime
        db_img: bytes = Utils.image_array_to_bytes(img_array)

        if isinstance(db_img, bytes):
            try:
                insert_stmt = sqlalchemy.insert(CACHE)
                insert_stmt = insert_stmt.values(
                    img=db_img,
                    src=src,
                    root=os.path.dirname(src),
                    size=size,
                    modified=modified,
                    catalog="",
                    colors="",
                    stars=""
                    )
                self.conn.execute(insert_stmt)

                select_query = sqlalchemy.select(STATS.c.size).where(STATS.c.name == "main")
                current_size = self.conn.execute(select_query).scalar() or 0
                new_size = current_size + len(db_img)

                update_query = sqlalchemy.update(STATS).where(STATS.c.name == "main").values(size=new_size)
                self.conn.execute(update_query)

                self.insert_count += 1
                if self.insert_count >= 10:
                    self.conn.commit()
                    self.insert_count = 0

            except (OperationalError, IntegrityError) as e:
                Utils.print_error(self, e)

    def create_img_array(self, src: str) -> ndarray | None:
        img = Utils.read_image(src)
        img = FitImg.start(img, Config.img_size)
        return img


# os.walk и чтение изображения происходит в отдельном QThread
# чтобы не блокировать основной интерфейс
# по мере того, как QThread находит и считывает изображение,
# в основной поток посылается сигнал и в сетку добавляется найденное изображение
# 
# во время поиска НЕ работает ресайз и сортировка сетки, поскольку сетка 
# до конца не сформирована
class GridSearch(Grid):
    search_finished = pyqtSignal()

    # для конекстного меню Thumbnail - "показать в папке"
    # программа переходит из поиска в исходную папку с изображением и выделяет его
    show_in_folder = pyqtSignal(str)

    def __init__(self, width: int, search_text: str):
        super().__init__(width)
        self.setAlignment(Qt.AlignmentFlag.AlignTop)

        # (путь до файла, имя файла, размер, дата изменения, тип файла)
        # этот словарик нужен для повторного формирования сетки при изменении
        # размера и для сортировки по имени/размеру/дате/типу
        self.sorted_widgets: dict[tuple: ThumbnailSearch] = {}

        self.col_count = Utils.get_clmn_count(width)
        self.row, self.col = 0, 0

        clmn_spacer = QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.grid_layout.addItem(clmn_spacer, 0, self.col_count + 1)

        self.search_thread = SearchFinder(search_text)
        self.search_thread.add_new_widget.connect(self.add_new_widget)
        self.search_thread._finished.connect(self.search_finished.emit)
        self.search_thread.start()

    def add_new_widget(self, widget_data: WidgetData):
        # data идет из сигнала _new_widget_sig
        # "src", "stats" - os.stat, "pixmap", "colors": str
        filename = os.path.basename(widget_data.src)
        colors = widget_data.colors
        wid = ThumbnailSearch(filename=filename, src=widget_data.src, path_to_wid=self.path_to_wid)
        wid.img_label.setPixmap(widget_data.pixmap)
        wid.update_colors(colors)

        wid.show_in_folder.connect(self.show_in_folder.emit)
        wid.move_to_wid.connect(self.move_to_wid)
        wid.clicked.connect(lambda r=self.row, c=self.col: self.select_new_widget((r, c)))
        self.grid_layout.addWidget(wid, self.row, self.col, alignment=Qt.AlignmentFlag.AlignTop)

        self.cell_to_wid[self.row, self.col] = wid
        self.wid_to_cell[wid] = (self.row, self.col)
        self.path_to_wid[widget_data.src] = wid

        # (путь до файла, имя файла, размер, дата изменения, тип файла)
        # этот словарик нужен для повторного формирования сетки при изменении
        # размера и для сортировки по имени/размеру/дате/типу
        size = widget_data.stats.st_size
        modified = widget_data.stats.st_mtime
        filetype = os.path.splitext(widget_data.src)[1]
        self.sorted_widgets[(widget_data.src, filename, size, modified, filetype, colors)] = wid

        # прибавляем строчку и столбец в сетку
        self.col += 1
        if self.col >= self.col_count:
            self.col = 0
            self.row += 1
 
    # если поиск еще идет, сетка не переформируется
    # если завершен, то мы формируем новую сетку на основе новых размеров
    def resize_grid(self, width: int):
        if not self.search_thread.isRunning():

            # очищаем для нового наполнения
            self.wid_to_cell.clear()
            self.cell_to_wid.clear()
            self.curr_cell = (0, 0)

            # получаем новое количество колонок на случай изменения размера окна
            col_count = Utils.get_clmn_count(width)
            row, col = 0, 0

            # (путь до файла, имя файла, размер, дата изменения, тип файла)
            # этот словарик нужен для повторного формирования сетки при изменении
            # размера и для сортировки по имени/размеру/дате/типу
            for wid in self.sorted_widgets.values():
                wid: ThumbnailSearch
                wid.disconnect()
                wid.show_in_folder.connect(self.show_in_folder.emit)
                wid.move_to_wid.connect(self.move_to_wid)
                wid.clicked.connect(lambda r=row, c=col: self.select_new_widget((r, c)))

                # обновляем информацию в Thumbnail о порядке путей и виджетов
                # для правильной передачи в ImgView после пересортировки сетки
                wid.path_to_wid = self.path_to_wid

                self.grid_layout.addWidget(wid, row, col, alignment=Qt.AlignmentFlag.AlignTop)
                self.cell_to_wid[row, col] = wid

                col += 1
                if col >= col_count:
                    col = 0
                    row += 1
            
            self.wid_to_cell = {v: k for k, v in self.cell_to_wid.items()}
    
    def sort_grid(self, width: int):
        sort_data = {"src": 0, "name": 1, "size": 2,  "modify": 3, "type": 4, "colors": 5}
        # ключи соответствуют json_data["sort"]
        # self.sorted_widgets = { (src, filename, size, modify, type, colors): SearchThumbnail }

        index = sort_data.get(Config.json_data.get("sort"))
        rev = Config.json_data.get("reversed")

        if index < 5:
            sort_key = lambda item: item[0][index]
        else:
            sort_key = lambda item: len(item[0][index])
            
        self.sorted_widgets = dict(
            sorted(self.sorted_widgets.items(), key=sort_key, reverse=rev)
            )
        
        # 
        # 
        # 
        # тут нужна пересортировка path_to_wid
        self.path_to_wid = {k[0]: v for k, v in self.sorted_widgets.items()}
        self.resize_grid(width)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        try:
            self.search_thread.disconnect()
        except TypeError:
            pass

        # устанавливаем флаг QThread на False чтобы прервать цикл os.walk
        # происходит session commit и не подается сигнал _finished
        self.search_thread._stop_cmd()