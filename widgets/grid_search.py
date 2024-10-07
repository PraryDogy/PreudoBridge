import os
from ast import literal_eval
from time import sleep

import sqlalchemy
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QPixmap
from PyQt5.QtWidgets import QAction, QSizePolicy, QSpacerItem, QFrame

from cfg import Config
from database import Cache, Dbase
from fit_img import FitImg
from utils import Utils

from .grid_base import Grid, GridMethods, Thumbnail


class _Thumbnail(Thumbnail):
    _show_in_folder = pyqtSignal(str)

    def __init__(self, filename: str, src: str, paths: list):
        super().__init__(filename, src, paths)

        self.context_menu.addSeparator()

        show_in_folder = QAction("Показать в папке", self)
        show_in_folder.triggered.connect(lambda: self._show_in_folder.emit(self.src))
        self.context_menu.addAction(show_in_folder) 


class _SearchFinderThread(QThread):
    _finished = pyqtSignal()
    _new_widget = pyqtSignal(dict)

    def __init__(self, search_dir: str, search_text: str):
        super().__init__()

        self.search_text: str = search_text
        self.search_dir: str = search_dir
        self.flag: bool = True
        self.session = Dbase.get_session()

    def _stop_cmd(self):
        self.flag: bool = False

    def run(self):
        try:
            self.search_text = literal_eval(self.search_text)
        except (ValueError, SyntaxError):
            pass

        if not isinstance(self.search_text, tuple):
            self.search_text = str(self.search_text)

        for root, _, files in os.walk(self.search_dir):
            if not self.flag:
                break

            for filename in files:
                if not self.flag:
                    break

                src: str = os.path.join(root, filename)
                src_lower: str = src.lower()

                if isinstance(self.search_text, tuple):
                    if src_lower.endswith(self.search_text):
                        self._create_wid(src)
                        continue

                elif self.search_text in filename and src_lower.endswith(Config.img_ext):
                    self._create_wid(src)
                    continue

        if self.flag:
            self._finished.emit()
        self.session.commit()

    def _create_wid(self, src: str):

        try:
            stats = os.stat(src)
        except (PermissionError, FileNotFoundError) as e:
            print("search grid > thread > error get os stat", e)
            return None

        pixmap: QPixmap = None
        db_img = self._get_db_image(src)

        if db_img is not None:
            pixmap: QPixmap = Utils.pixmap_from_bytes(db_img)

        else:
            new_img = self._create_new_image(src)
            self._image_to_db(src, new_img, stats)

            if new_img is not None:
                pixmap = Utils.pixmap_from_array(new_img)

        if not pixmap:
            pixmap = QPixmap("images/file_210.png")

        self._new_widget.emit({"src": src, "stats": stats, "pixmap": pixmap})
        sleep(0.2)

    def _get_db_image(self, src: str) -> bytes | None:
        q = sqlalchemy.select(Cache.img).where(Cache.src==src)
        res = self.session.execute(q).first()
        if res:
            return res[0]
        return None

    def _image_to_db(self, src: str, img_array, stats: os.stat_result):
        size = stats.st_size
        modified = stats.st_mtime
        db_img = Utils.image_array_to_bytes(img_array)

        if db_img is not None:
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
            except Exception as e:
                print("search thread insert db image error: ", e)

    def _create_new_image(self, src: str):
        img = Utils.read_image(src)
        img = FitImg.start(img, Config.thumb_size)
        return img


class _GridSearchBase(Grid):
    search_finished = pyqtSignal()
    show_thumbnail_in_folder = pyqtSignal(str)

    def __init__(self, width: int, search_text: str):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._image_grid_widgets: dict[tuple: _Thumbnail] = {}
        self.search_text = search_text

        self.col_count = Utils.get_clmn_count(width)
        if self.col_count < 1:
            self.col_count = 1
        self.row_count, self.local_col = 0, 0

        clmn_spacer = QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.grid_layout.addItem(clmn_spacer, 0, self.col_count + 1)

        self._thread = _SearchFinderThread(Config.json_data["root"], search_text)
        self._thread._new_widget.connect(self._add_new_widget)
        self._thread._finished.connect(self.search_finished.emit)
        self._thread.start()

    def _add_new_widget(self, data: dict):
        filename = os.path.basename(data.get("src"))
        wid = _Thumbnail(filename=filename, src=data.get("src"), paths=self._paths)
        wid.img_label.setPixmap(data.get("pixmap"))
        wid._show_in_folder.connect(self.show_thumbnail_in_folder.emit)
        wid._move_to_wid_sig.connect(self._move_to_wid)
        wid._clicked_sig.connect(lambda wid=wid: self._clicked_thumb(wid))  

        self.grid_layout.addWidget(wid, self.row_count, self.local_col, alignment=Qt.AlignmentFlag.AlignTop)

        self._row_col_widget[self.row_count, self.local_col_count] = wid
        self._widget_row_col[wid] = (self.row_count, self.local_col_count)
        self._path_widget[data.get("src")] = wid
        self._widget_path[wid] = data.get("src")
        self._paths.append(data.get("src"))

        self.local_col_count += 1
        if self.local_col_count >= self.col_count:
            self.local_col_count = 0
            self.row_count += 1

        stats: os.stat_result = data.get("stats")
        size = stats.st_size
        modified = stats.st_mtime
        filetype = os.path.splitext(data.get("src"))[1]
        self._image_grid_widgets[(data.get("src"), filename, size, modified, filetype)] = wid

    def _clicked_thumb(self, widget: Thumbnail):
        self._frame_selected_widget(QFrame.Shape.NoFrame)
        self.cur_row, self.cur_col = self._widget_row_col.get(widget)
        self._selected_thumbnail = widget
        self._frame_selected_widget(QFrame.Shape.Panel)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        try:
            self._thread.disconnect()
        except TypeError:
            pass
        self._thread._stop_cmd()
        # return super().closeEvent(a0)
  

class GridSearch(_GridSearchBase, GridMethods):
    def __init__(self, width: int, search_text: str):
        super().__init__(width, search_text)

    def resize_grid(self, width: int):
        if not self._thread.isRunning():

            self._row_col_widget.clear()
            self._widget_row_col.clear()

            self.col_count = Utils.get_clmn_count(width)
            if self.col_count < 1:
                self.col_count = 1
            self.row_count, self.local_col_count = 0, 0

            for data, wid in self._image_grid_widgets.items():
                self.grid_layout.addWidget(wid, self.row_count, self.local_col_count, alignment=Qt.AlignmentFlag.AlignTop)

                self._row_col_widget[self.row_count, self.local_col_count] = wid
                self._widget_row_col[wid] = (self.row_count, self.local_col_count)

                self.local_col_count += 1
                if self.local_col_count >= self.col_count:
                    self.local_col_count = 0
                    self.row_count += 1

    def stop_and_wait_threads(self):
        self._thread._stop_cmd()
        self._thread.wait()

    def sort_grid(self, width: int):
        sort_data = {"name": 1, "size": 2,  "modify": 3, "type": 4}
        # начинаем с 1, потому что 0 у нас src, нам не нужна сортировка по src
        # ключи соответствуют json_data["sort"]

        index = sort_data.get(Config.json_data.get("sort"))
        self._image_grid_widgets = dict(
            sorted(self._image_grid_widgets.items(), key=lambda item: item[0][index])
            )

        if Config.json_data["reversed"]:
            self._image_grid_widgets = dict(reversed(self._image_grid_widgets.items()))

        self.resize_grid(width)

    def move_to_wid(self, src: str):
        self._move_to_wid(src)