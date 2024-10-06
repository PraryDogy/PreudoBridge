import os
import subprocess

import numpy as np
import sqlalchemy
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QContextMenuEvent, QKeyEvent, QMouseEvent, QPixmap
from PyQt5.QtWidgets import (QAction, QFrame, QGridLayout, QLabel, QMenu,
                             QScrollArea, QSizePolicy, QSpacerItem, QWidget)

from cfg import Config
from database import Cache, Dbase
from fit_img import FitImg
from utils import Utils

from .grid_base import Thumbnail, GridCustom
from .win_img_view import WinImgView

class _Storage:
    threads: list = []


class _LoadImagesThread(QThread):
    _stop_thread = pyqtSignal()
    _finished = pyqtSignal()
    
    def __init__(self, grid_widgets: dict[tuple: QLabel]):
        super().__init__()

        self.grid_widgets: dict[tuple: QLabel] = grid_widgets
        self.remove_db_images: dict[tuple: str] = {}
        self.db_images: dict = {}
        
        self.flag = True
        self._stop_thread.connect(self._stop_thread_cmd)

        self.session = Dbase.get_session()

    def run(self):
        # print(self, "thread started")
        self.db_images: dict = self._get_db_images()
        self._load_already_images()
        self._create_new_images()
        self._remove_images()
        self.session.commit()
        self.session.close()
        self._finished.emit()
        # print(self, "thread finished")

    def _create_new_images(self):
        grid_widgets = self.grid_widgets.copy()

        for (src, size, modified), widget in grid_widgets.items():
            if not self.flag:
                break

            if os.path.isdir(src):
                continue

            img = Utils.read_image(src)
            img = FitImg.start(img, Config.thumb_size)

            try:
                self._set_new_image(widget, img)
            except AttributeError as e:
                pass

            try:
                img = Utils.image_array_to_bytes(img)
                q = sqlalchemy.insert(Cache)
                q = q.values({
                    "img": img,
                    "src": src,
                    "root": Config.json_data["root"],
                    "size": size,
                    "modified": modified
                    })
                self.session.execute(q)
            except Exception as e:
                # print(e)
                pass

    def _load_already_images(self):
        for (src, size, modified), bytearray_image in self.db_images.items():
            widget: QLabel = self.grid_widgets.get((src, size, modified))

            if not self.flag:
                break

            if widget:
                pixmap: QPixmap = Utils.pixmap_from_bytes(bytearray_image)
                widget.setPixmap(pixmap)
                self.grid_widgets.pop((src, size, modified))
            else:
                self.remove_db_images[(src, size, modified)] = ""

    def _remove_images(self):
        for (src, _, _), _ in self.remove_db_images.items():
            q = sqlalchemy.delete(Cache)
            q = q.where(Cache.src==src)
            self.session.execute(q)

    def _get_db_images(self):
        q = sqlalchemy.select(Cache.img, Cache.src, Cache.size, Cache.modified)
        q = q.where(Cache.root==Config.json_data["root"])
        res = self.session.execute(q).fetchall()
        return {
            (src, size, modified): img
            for img, src, size,  modified in res
            }

    def _stop_thread_cmd(self):
        self.flag = False

    def _set_new_image(self, widget: QLabel, image: np.ndarray):
        pixmap = Utils.pixmap_from_array(image)
        try:
            widget.setPixmap(pixmap)
        except RuntimeError:
            pass


class _LoadFinderItems:
    def __init__(self):
        super().__init__()
        self.finder_items: dict = {}

    def _get(self):
        try:
            self._get_items()
            self._sort_items()
        except (PermissionError, FileNotFoundError):
            self.finder_items: dict = {}
        
        return self.finder_items

    def _get_items(self):
        for item in os.listdir(Config.json_data["root"]):
            src: str = os.path.join(Config.json_data["root"], item)

            try:
                stats = os.stat(src)
            except (PermissionError, FileNotFoundError):
                continue

            size = stats.st_size
            modified = stats.st_mtime
            filetype = os.path.splitext(item)[1]

            if src.lower().endswith(Config.img_ext):
                self.finder_items[(src, item, size, modified, filetype)] = None
                continue

            elif os.path.isdir(src):
                self.finder_items[(src, item, size, modified, filetype)] = None
            
    def _sort_items(self):
        sort_data = {"name": 1, "size": 2,  "modify": 3, "type": 4}
        # начинаем с 1, потому что 0 у нас src, нам не нужна сортировка по src

        index = sort_data.get(Config.json_data["sort"])
        self.finder_items = dict(
            sorted(self.finder_items.items(), key=lambda item: item[0][index])
            )

        if Config.json_data["reversed"]:
            self.finder_items = dict(reversed(self.finder_items.items()))


class _FolderThumbnail(Thumbnail):
    _add_fav_sig = pyqtSignal(str)
    _del_fav_sig = pyqtSignal(str)
    _open_folder_sig = pyqtSignal(str)

    def __init__(self, filename: str, src: str):
        super().__init__(filename, src)

        self.context_menu = QMenu(self)

        view_action = QAction("Просмотр", self)
        view_action.triggered.connect(lambda: self._open_folder_sig.emit(self.src))
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
            del_fav = QAction("Удалить из избранного", self)
            del_fav.triggered.connect(lambda: self._del_fav_sig.emit(self.src))
            self.context_menu.addAction(del_fav)

        else:
            add_fav = QAction("Добавить в избранное", self)
            add_fav.triggered.connect(lambda: self._add_fav_sig.emit(self.src))
            self.context_menu.addAction(add_fav)

    def mouseDoubleClickEvent(self, a0: QMouseEvent | None) -> None:
        self._open_folder_sig.emit(self.src)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        self.select_thumbnail()
        self.context_menu.exec_(self.mapToGlobal(a0.pos()))


class _GridStandartBase(GridCustom):
    add_fav_sig = pyqtSignal(str)
    del_fav_sig = pyqtSignal(str)
    open_folder_sig = pyqtSignal(str)

    def __init__(self, width: int):
        super().__init__()

        self.image_grid_widgets: dict = {}
        self.all_grid_widgets: list = []

        clmn_count = Utils.get_clmn_count(width)
        if clmn_count < 1:
            clmn_count = 1

        row, col = 0, 0

        finder_items = _LoadFinderItems()
        finder_items = finder_items._get()

        for (src, filename, size, modified, _), _ in finder_items.items():
            if os.path.isdir(src):
                thumbnail = _FolderThumbnail(filename, src)
                self._set_default_image(thumbnail.img_label, "images/folder_210.png")
                thumbnail._open_folder_sig.connect(self.open_folder_sig.emit)
                thumbnail._add_fav_sig.connect(self.add_fav_sig.emit)
                thumbnail._del_fav_sig.connect(self.del_fav_sig.emit)

            else:
                thumbnail = Thumbnail(filename, src)
                thumbnail._move_to_wid_sig.connect(lambda src: self._move_to_wid(src))
                self._set_default_image(thumbnail.img_label, "images/file_210.png")

                Config.image_grid_widgets[src] = thumbnail
                self.image_grid_widgets[(src, size, modified)] = thumbnail.img_label

            self.grid_layout.addWidget(thumbnail, row, col)

            col += 1
            if col >= clmn_count:
                col = 0
                row += 1

            self.all_grid_widgets.append(thumbnail)

        if self.all_grid_widgets:
            row_spacer = QSpacerItem(1, 1, QSizePolicy.Minimum, QSizePolicy.Expanding)
            self.grid_layout.addItem(row_spacer, row + 1, 0)
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

    def _move_to_wid(self, src: str):
        try:
            wid: Thumbnail = Config.image_grid_widgets.get(src)
            wid.select_thumbnail()
            self.ensureWidgetVisible(wid)
        except (RuntimeError, KeyError) as e:
            print("move to wid error: ", e)

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
        new_thread = _LoadImagesThread(self.image_grid_widgets)
        _Storage.threads.append(new_thread)
        new_thread.start()

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self._stop_threads()
        return super().closeEvent(a0)
        

class GridStandart(_GridStandartBase):
    def __init__(self, width: int):
        super().__init__(width)

    def rearrange(self, width: int):
        clmn_count = Utils.get_clmn_count(width)
        
        if clmn_count < 1:
            clmn_count = 1

        row, col = 0, 0

        for wid in self.all_grid_widgets:
            self.grid_layout.addWidget(wid, row, col)
            col += 1
            if col >= clmn_count:
                col = 0
                row += 1
        return
    
    def stop_and_wait_threads(self):
        for thread in _Storage.threads:
            thread: _LoadImagesThread
            thread._stop_thread.emit()
            thread.wait()

    def rearrange_sorted(self, width: int):
        self.rearrange(width)

    def move_to_wid(self, src: str):
        self._move_to_wid(src)