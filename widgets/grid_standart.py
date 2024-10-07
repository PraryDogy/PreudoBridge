import os

import numpy as np
import sqlalchemy
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QContextMenuEvent, QMouseEvent, QPixmap
from PyQt5.QtWidgets import (QAction, QFrame, QLabel, QMenu, QSizePolicy,
                             QSpacerItem)

from cfg import Config
from database import Cache, Dbase
from fit_img import FitImg
from utils import Utils

from .grid_base import Grid, GridMethods, Thumbnail


class _Storage:
    threads: list = []


class _LoadImagesThread(QThread):
    _stop_thread = pyqtSignal()
    _finished = pyqtSignal()
    
    def __init__(self, grid_widgets: dict[tuple: QLabel]):
        super().__init__()

        self.grid_widgets: dict[tuple: QLabel] = grid_widgets
        self.remove_db_images: dict[tuple: None] = {}
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
                    "root": Config.json_data.get("root"),
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
                self.remove_db_images[(src, size, modified)] = None

    def _remove_images(self):
        for (src, _, _), _ in self.remove_db_images.items():
            q = sqlalchemy.delete(Cache)
            q = q.where(Cache.src==src)
            self.session.execute(q)

    def _get_db_images(self):
        q = sqlalchemy.select(Cache.img, Cache.src, Cache.size, Cache.modified)
        q = q.where(Cache.root==Config.json_data.get("root"))
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
        self.finder_items: dict[tuple: None] = {}

    def _get(self):
        try:
            self._get_items()
            self._sort_items()
        except (PermissionError, FileNotFoundError):
            self.finder_items: dict[tuple: None] = {}
        
        return self.finder_items

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
    _add_fav_sig = pyqtSignal(str)
    _del_fav_sig = pyqtSignal(str)
    _open_folder_sig = pyqtSignal(str)

    def __init__(self, filename: str, src: str):
        super().__init__(filename, src, [])

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

    def _view_file(self):
        self._open_folder_sig.emit(self.src)

    def mouseDoubleClickEvent(self, a0: QMouseEvent | None) -> None:
        self._open_folder_sig.emit(self.src)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        self.clicked_cmd()
        self.context_menu.exec_(self.mapToGlobal(a0.pos()))


class _GridStandartBase(Grid):
    add_fav_sig = pyqtSignal(str)
    del_fav_sig = pyqtSignal(str)
    open_folder_sig = pyqtSignal(str)

    def __init__(self, width: int):
        super().__init__()

        _finder_items = _LoadFinderItems()
        _finder_items = _finder_items._get()

        clmn_count = Utils.get_clmn_count(width)
        if clmn_count < 1:
            clmn_count = 1

        self.row_count, self.col_count = 0, 0

        # (src, size, modified): QLabel. Для последующей загрузки в _LoadImagesThread
        self._image_grid_widgets: dict[tuple: QPixmap] = {}

        for (src, filename, size, modified, _), _ in _finder_items.items():

            if os.path.isdir(src):
                wid = _FolderThumbnail(filename, src)
                self._set_default_image(wid.img_label, "images/folder_210.png")
                wid._open_folder_sig.connect(self.open_folder_sig.emit)
                wid._add_fav_sig.connect(self.add_fav_sig.emit)
                wid._del_fav_sig.connect(self.del_fav_sig.emit)

            else:
                wid = Thumbnail(filename, src, self._paths)
                wid._move_to_wid_sig.connect(lambda src: self._move_to_wid(src))
                self._set_default_image(wid.img_label, "images/file_210.png")
                self._image_grid_widgets[(src, size, modified)] = wid.img_label

            self._add_wid_to_dicts({"row": self.row_count, "col": self.col_count, "src": src, "widget": wid})
            wid._clicked_sig.connect(lambda wid=wid: self._clicked_thumb(wid))

            self.grid_layout.addWidget(wid, self.row_count, self.col_count)

            self.col_count += 1
            if self.col_count >= clmn_count:
                self.col_count = 0
                self.row_count += 1

        if self._row_col_widget:
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

    def _clicked_thumb(self, widget: Thumbnail):
        self._frame_selected_widget(QFrame.Shape.NoFrame)
        self.cur_row, self.cur_col = self._widget_row_col.get(widget)
        self._selected_thumbnail = widget
        self._frame_selected_widget(QFrame.Shape.Panel)

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
        _Storage.threads.append(new_thread)
        new_thread.start()

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self._stop_threads()
        return super().closeEvent(a0)
        

class GridStandart(_GridStandartBase, GridMethods):
    def __init__(self, width: int):
        super().__init__(width)

    def resize_grid(self, width: int):
        row_col_widget = self._row_col_widget.copy()
        self._reset_row_cols()

        clmn_count = Utils.get_clmn_count(width)
        if clmn_count < 1:
            clmn_count = 1

        self.row_count, self.col_count = 0, 0

        for (row, col), wid in row_col_widget.items():

            self.grid_layout.addWidget(wid, self.row_count, self.col_count)

            src = self._widget_path.get(wid)
            self._add_wid_to_dicts({"row": self.row_count, "col": self.col_count, "src": src, "widget": wid})

            self.col_count += 1
            if self.col_count >= clmn_count:
                self.col_count = 0
                self.row_count += 1

    def stop_and_wait_threads(self):
        for thread in _Storage.threads:
            thread: _LoadImagesThread
            thread._stop_thread.emit()
            thread.wait()

    def sort_grid(self, width: int):
        self.resize_grid(width)

    def move_to_wid(self, src: str):
        self._move_to_wid(src)