import os
from ast import literal_eval
from time import sleep

import sqlalchemy
from numpy import ndarray
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QContextMenuEvent, QPixmap
from PyQt5.QtWidgets import QAction, QSizePolicy, QSpacerItem
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import Config, JsonData
from database import CACHE, STATS, Engine
from fit_img import FitImg
from utils import Utils

from .grid_base import Grid, Thumbnail


class ThumbnailSearch(Thumbnail):
    show_in_folder = pyqtSignal(str)

    def __init__(self, name: str, src: str, path_to_wid: dict[str: Thumbnail]):
        super().__init__(name, 0, 0, "", src, path_to_wid)

        self.context_menu.addSeparator()

        show_in_folder = QAction("Показать в папке", self)
        show_in_folder.triggered.connect(lambda: self.show_in_folder.emit(self.src))
        self.context_menu.addAction(show_in_folder)


class WidgetData:
    def __init__(self, src: str, colors: str, rating: int, stats: os.stat_result, pixmap: QPixmap):
        self.src: str = src
        self.colors: str = colors
        self.rating: int = rating
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
        self.db_size: int = 0

    def run(self):
        self.get_db_size()

        try:
            self.search_text: tuple = literal_eval(self.search_text)
        except (ValueError, SyntaxError):
            pass

        if not isinstance(self.search_text, tuple):
            self.search_text: str = str(self.search_text)

        for root, _, files in os.walk(JsonData.root):
            if not self.flag:
                break

            for file in files:
                if not self.flag:
                    break

                file_path: str = os.path.join(root, file)
                file_path_lower: str = file_path.lower()


                if file_path_lower.endswith(Config.IMG_EXT):

                    if isinstance(self.search_text, tuple):
                        self.create_wid(file_path)

                    elif self.search_text in file:
                        self.create_wid(file_path)

        if self.insert_count > 0:
            try:
                self.conn.commit()
            except (IntegrityError, OperationalError) as e:
                Utils.print_error(self, e)

        self.update_db_size()
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
        rating: int = 0

        db_data: dict = self.get_img_data_db(src)

        if isinstance(db_data, dict):
            pixmap: QPixmap = Utils.pixmap_from_bytes(db_data.get("img"))
            colors = db_data.get("colors")
            rating = db_data.get("rating")

        else:
            img_array: ndarray = self.create_img_array(src)
            self.img_data_to_db(src, img_array, stats)

            if isinstance(img_array, ndarray):
                pixmap = Utils.pixmap_from_array(img_array)

        if not pixmap:
            pixmap = QPixmap("images/file_210.png")

        self.add_new_widget.emit(WidgetData(src, colors, rating, stats, pixmap))
        sleep(0.1)

    def get_img_data_db(self, src: str) -> dict | None:
        try:
            sel_stmt = sqlalchemy.select(CACHE.c.img, CACHE.c.colors, CACHE.c.rating).where(CACHE.c.src == src)
            res = self.conn.execute(sel_stmt).first()

            if res:
                return {"img": res.img, "colors": res.colors, "rating": res.rating}
            else:
                return None

        except OperationalError as e:
            Utils.print_error(self, e)
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
                    rating=0
                    )
                self.conn.execute(insert_stmt)

                self.insert_count += 1
                if self.insert_count >= 10:
                    self.conn.commit()
                    self.insert_count = 0

                self.db_size += len(db_img)

            except (OperationalError, IntegrityError) as e:
                Utils.print_error(self, e)

    def create_img_array(self, src: str) -> ndarray | None:
        img = Utils.read_image(src)
        img = FitImg.start(img, Config.IMG_SIZE)
        return img

    def stop_cmd(self):
        self.flag: bool = False

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


class GridSearch(Grid):
    search_finished = pyqtSignal()

    # для конекстного меню Thumbnail - "показать в папке"
    # программа переходит из поиска в исходную папку с изображением и выделяет его
    show_in_folder = pyqtSignal(str)

    def __init__(self, width: int, search_text: str):
        super().__init__()
        self.ww = width

        self.col_count = Utils.get_clmn_count(width)
        self.row, self.col = 0, 0

        clmn_spacer = QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.grid_layout.addItem(clmn_spacer, 0, self.col_count + 1)

        self.search_thread = SearchFinder(search_text)
        self.search_thread.add_new_widget.connect(self.add_new_widget)
        self.search_thread._finished.connect(self.search_finished.emit)
        self.search_thread.start()

    def add_new_widget(self, widget_data: WidgetData):
        name = os.path.basename(widget_data.src)
        wid = ThumbnailSearch(name=name, src=widget_data.src, path_to_wid=self.path_to_wid)

        wid.img_label.setPixmap(widget_data.pixmap)

        # устанавливаем аттрибуты для сортировки
        wid.set_colors(widget_data.colors)
        wid.set_rating(widget_data.rating)
        wid.size = widget_data.stats.st_size
        wid.modified = widget_data.stats.st_mtime
        wid.filetype = os.path.splitext(widget_data.src)[1]

        wid.show_in_folder.connect(self.show_in_folder.emit)
        wid.move_to_wid.connect(self.move_to_wid)
        wid.clicked.connect(lambda r=self.row, c=self.col: self.select_new_widget((r, c)))
        wid.sort_click.connect(lambda: self.sort_grid(self.ww))

        self.grid_layout.addWidget(wid, self.row, self.col)

        self.cell_to_wid[self.row, self.col] = wid
        self.wid_to_cell[wid] = (self.row, self.col)
        self.path_to_wid[widget_data.src] = wid

        self.sorted_widgets.append(wid)

        # прибавляем строчку и столбец в сетку
        self.col += 1
        if self.col >= self.col_count:
            self.col = 0
            self.row += 1
 
    # если поиск еще идет, сетка не переформируется
    # если завершен, то мы формируем новую сетку на основе новых размеров
    def resize_grid(self, width: int):
        if not self.search_thread.isRunning():

            self.wid_to_cell.clear()
            self.cell_to_wid.clear()
            self.curr_cell = (0, 0)

            col_count = Utils.get_clmn_count(width)
            row, col = 0, 0

            for wid in self.sorted_widgets:

                if wid.isHidden():
                    continue

                wid: ThumbnailSearch
                wid.disconnect()
                wid.show_in_folder.connect(self.show_in_folder.emit)
                wid.move_to_wid.connect(self.move_to_wid)
                wid.clicked.connect(lambda r=row, c=col: self.select_new_widget((r, c)))
                wid.sort_click.connect(lambda: self.sort_grid(width))

                # обновляем информацию в Thumbnail о порядке путей и виджетов
                # для правильной передачи в ImgView после пересортировки сетки
                wid.path_to_wid = self.path_to_wid

                self.grid_layout.addWidget(wid, row, col)
                self.cell_to_wid[row, col] = wid

                col += 1
                if col >= col_count:
                    col = 0
                    row += 1
            
            self.wid_to_cell = {v: k for k, v in self.cell_to_wid.items()}
    
    def sort_grid(self, width: int):
        if not self.sorted_widgets:
            return

        if JsonData.sort == "colors":
            key = lambda x: len(getattr(x, JsonData.sort))
        else:
            key = lambda x: getattr(x, JsonData.sort)
        rev = JsonData.reversed
        self.sorted_widgets = sorted(self.sorted_widgets, key=key, reverse=rev)
        
        self.path_to_wid = {
            wid.src: wid
            for wid in self.sorted_widgets
            if isinstance(wid, Thumbnail)
            }

        self.reset_selection()
        self.resize_grid(width)

    def filter_grid(self, width: int):
        for wid in self.sorted_widgets:
            wid: ThumbnailSearch
            show_widget = True

            if Config.rating_filter > 0:
                if not (Config.rating_filter >= wid.rating > 0):
                    show_widget = False

            if Config.color_filters:
                if not any(color for color in wid.colors if color in Config.color_filters):
                    show_widget = False

            if show_widget:
                wid.show()
            else:
                wid.hide()

        self.reset_selection()
        self.resize_grid(width)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        try:
            self.search_thread.disconnect()
        except TypeError:
            pass

        # устанавливаем флаг QThread на False чтобы прервать цикл os.walk
        # происходит session commit и не подается сигнал _finished
        self.search_thread.stop_cmd()