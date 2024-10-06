import os
from ast import literal_eval
from time import sleep

import sqlalchemy
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QPixmap
from PyQt5.QtWidgets import QAction, QSizePolicy, QSpacerItem

from cfg import Config
from database import Cache, Dbase
from fit_img import FitImg
from utils import Utils

from .grid_base import GridCustom, Thumbnail


class _Thumbnail(Thumbnail):
    _show_in_folder = pyqtSignal(str)

    def __init__(self, filename: str, src: str):
        super().__init__(filename, src)

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
        except ValueError:
            pass

        if not isinstance(self.search_text, tuple):
            self.search_text = str(self.search_text)

        for root, dirs, files in os.walk(self.search_dir):
            if not self.flag:
                break

            for filename in files:
                if not self.flag:
                    break

                src: str = os.path.join(root, filename)
                src_lower: str = src.lower()

                if isinstance(self.search_text, tuple):
                    if src_lower.endswith(self.search_text):
                        self._create_wid(src, filename)
                        continue

                elif self.search_text in filename and src_lower.endswith(Config.img_ext):
                    self._create_wid(src, filename)
                    continue

        if self.flag:
            self._finished.emit()
        self.session.commit()

    def _create_wid(self, src: str, filename: str):
        pixmap: QPixmap = None
        db_img = self._get_db_image(src)

        if db_img is not None:
            pixmap: QPixmap = Utils.pixmap_from_bytes(db_img)

        else:
            new_img = self._create_new_image(src)
            self._image_to_db(src, new_img)

            if new_img is not None:
                pixmap = Utils.pixmap_from_array(new_img)

        if not pixmap:
            pixmap = QPixmap("images/file_210.png")

        self._new_widget.emit({
            "src": src,
            "filename": filename,
            "pixmap": pixmap
            })
        sleep(0.2)

    def _get_db_image(self, src: str) -> bytes | None:
        q = sqlalchemy.select(Cache.img).where(Cache.src==src)
        res = self.session.execute(q).first()
        if res:
            return res[0]
        return None

    def _image_to_db(self, src: str, img_array):
        try:
            stats = os.stat(src)
        except (PermissionError, FileNotFoundError):
            return None

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


class _GridSearchBase(GridCustom):
    search_finished = pyqtSignal()
    show_thumbnail_in_folder = pyqtSignal(str)

    def __init__(self, width: int, search_text: str):
        super().__init__()
        self.image_grid_widgets: dict[tuple: QPixmap] = {}
        self.search_text = search_text
        self.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.clmn_count = Utils.get_clmn_count(width)
        if self.clmn_count < 1:
            self.clmn_count = 1
        self.row, self.col = 0, 0

        clmn_spacer = QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.grid_layout.addItem(clmn_spacer, 0, self.clmn_count + 1)

        self._thread = _SearchFinderThread(Config.json_data["root"], search_text)
        self._thread._new_widget.connect(self._add_new_widget)
        self._thread._finished.connect(self.search_finished.emit)
        self._thread.start()

    def _add_new_widget(self, data: dict):
        widget = _Thumbnail(filename=data.get("filename"), src=data.get("src"))
        widget.img_label.setPixmap(data.get("pixmap"))
        widget._show_in_folder.connect(self.show_thumbnail_in_folder.emit)
        widget._move_to_wid_sig.connect(self._move_to_wid)

        self.grid_layout.addWidget(widget, self.row, self.col, alignment=Qt.AlignmentFlag.AlignTop)
        Config.image_grid_widgets[data.get("src")] = widget

        self.col += 1
        if self.col >= self.clmn_count:
            self.col = 0
            self.row += 1

    def _move_to_wid(self, src: str):
        try:
            wid: _Thumbnail = Config.image_grid_widgets.get(src)
            wid.select_thumbnail()
            self.ensureWidgetVisible(wid)
        except (RuntimeError, KeyError) as e:
            print("move to wid error: ", e)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        try:
            self._thread.disconnect()
        except TypeError:
            pass
        self._thread._stop_cmd()
        # return super().closeEvent(a0)
  

class GridSearch(_GridSearchBase):
    def __init__(self, width: int, search_text: str):
        super().__init__(width, search_text)

    def rearrange(self, width: int):
        widgets = self.findChildren(_Thumbnail)
        
        self.clmn_count = Utils.get_clmn_count(width)
        if self.clmn_count < 1:
            self.clmn_count = 1
        self.row, self.col = 0, 0

        for wid in widgets:
            self.grid_layout.addWidget(wid, self.row, self.col)
            self.col += 1
            if self.col >= self.clmn_count:
                self.col = 0
                self.row += 1

    def stop_and_wait_threads(self):
        self._thread._stop_cmd()
        self._thread.wait()

    def rearrange_sorted(self, width: int):
        ...

    def move_to_wid(self, src: str):
        self._move_to_wid(src)