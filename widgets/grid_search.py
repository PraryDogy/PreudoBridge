import os
import subprocess
from time import sleep

import sqlalchemy
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QContextMenuEvent, QMouseEvent, QPixmap
from PyQt5.QtWidgets import (QAction, QFrame, QGridLayout, QMenu, QScrollArea,
                             QSizePolicy, QSpacerItem, QWidget)

from cfg import Config
from database import Cache, Dbase
from fit_img import FitImg
from utils import Utils

from .grid_base import Thumbnail
from .win_img_view import WinImgView


class Thumbnail(Thumbnail):
    _move_to_widget = pyqtSignal(str)
    _show_in_folder = pyqtSignal(str)

    def __init__(self, filename: str, src: str):
        super().__init__(filename, src)

    def mouseDoubleClickEvent(self, a0: QMouseEvent | None) -> None:
        if a0.button() == Qt.MouseButton.LeftButton:
            self.setFrameShape(QFrame.Shape.Panel)
            QTimer.singleShot(500, lambda: self.setFrameShape(QFrame.Shape.NoFrame))
            self.win = WinImgView(self, self.src)
            Utils.center_win(parent=Utils.get_main_win(), child=self.win)
            self.win.closed.connect(lambda src: self._move_to_widget.emit(src))
            self.win.show()
        return super().mouseDoubleClickEvent(a0)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:

        self.setFrameShape(QFrame.Shape.Panel)

        context_menu = QMenu(self)

        view_action = QAction("Просмотр", self)
        view_action.triggered.connect(self.view_file)
        context_menu.addAction(view_action)

        context_menu.addSeparator()

        open_action = QAction("Открыть по умолчанию", self)
        open_action.triggered.connect(self.open_default)
        context_menu.addAction(open_action)

        show_in_finder_action = QAction("Показать в Finder", self)
        show_in_finder_action.triggered.connect(self.show_in_finder)
        context_menu.addAction(show_in_finder_action)

        copy_path = QAction("Скопировать путь до файла", self)
        copy_path.triggered.connect(lambda: Utils.copy_path(self.src))
        context_menu.addAction(copy_path)

        context_menu.addSeparator()

        show_in_folder = QAction("Показать в папке", self)
        show_in_folder.triggered.connect(lambda: self._show_in_folder.emit(self.src))
        context_menu.addAction(show_in_folder) 

        context_menu.exec_(self.mapToGlobal(a0.pos()))

        self.setFrameShape(QFrame.Shape.NoFrame)

        return super().contextMenuEvent(a0)

    def view_file(self):
        if self.src.endswith(Config.img_ext):
            self.win = WinImgView(self, self.src)
            self.win.closed.connect(lambda src: self._move_to_widget.emit(src))
            main_win = Utils.get_main_win()
            Utils.center_win(parent=main_win, child=self.win)
            self.win.show()

    def open_default(self):
        subprocess.call(["open", self.src])

    def show_in_finder(self):
        subprocess.call(["open", "-R", self.src])


class SearchFinderThread(QThread):
    _finished = pyqtSignal()
    _new_widget = pyqtSignal(dict)

    def __init__(self, search_dir: str, search_text: str):
        super().__init__()

        self.search_text: str = search_text
        self.search_dir: str = search_dir
        self.flag: bool = True
        self.session = Dbase.get_session()

    def stop_cmd(self):
        self.flag: bool = False

    def run(self):
        for root, dirs, files in os.walk(self.search_dir):
            if not self.flag:
                break

            for filename in files:
                if not self.flag:
                    break

                src = os.path.join(root, filename)

                if self.search_text in filename and src.endswith(Config.img_ext):
                    self.create_wid(src, filename)

        if self.flag:
            self._finished.emit()
        self.session.commit()

    def create_wid(self, src: str, filename: str):
        pixmap: QPixmap = None
        db_img = self.get_db_image(src)

        if db_img is not None:
            pixmap: QPixmap = Utils.pixmap_from_bytes(db_img)

        else:
            new_img = self.create_new_image(src)
            self.image_to_db(src, new_img)

            if new_img is not None:
                pixmap = Utils.pixmap_from_array(new_img)

        if not pixmap:
            pixmap = QPixmap("images/file_210.png")

        self._new_widget.emit({"src": src, "filename": filename, "pixmap": pixmap})
        sleep(0.1)

    def get_db_image(self, src: str) -> bytes | None:
        q = sqlalchemy.select(Cache.img).where(Cache.src==src)
        res = self.session.execute(q).first()
        if res:
            return res[0]
        return None

    def image_to_db(self, src: str, img_array):
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

    def create_new_image(self, src: str):
        img = Utils.read_image(src)
        img = FitImg.start(img, Config.thumb_size)
        return img


class GridSearchBase(QScrollArea):
    search_finished = pyqtSignal()
    show_in_folder = pyqtSignal(str)
    move_to_widget = pyqtSignal(str)

    def __init__(self, width: int, search_text: str):
        super().__init__()
        self.search_text = search_text
        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignmentFlag.AlignTop)

        Config.img_viewer_images.clear()

        self.clmn_count = width // Config.thumb_size
        if self.clmn_count < 1:
            self.clmn_count = 1
        self.row, self.col = 0, 0

        main_wid = QWidget()
        self.grid_layout = QGridLayout(main_wid)
        self.grid_layout.setSpacing(5)
        self.setWidget(main_wid)

        clmn_spacer = QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.grid_layout.addItem(clmn_spacer, 0, self.clmn_count + 1)

        self.search_thread = SearchFinderThread(Config.json_data["root"], search_text)
        self.search_thread._new_widget.connect(self._add_new_widget)
        self.search_thread._finished.connect(self.search_finished.emit)
        self.search_thread.start()

    def _add_new_widget(self, data: dict):
        widget = Thumbnail(filename=data["filename"], src=data["src"])
        widget.img_label.setPixmap(data["pixmap"])
        widget._show_in_folder.connect(self.show_in_folder.emit)
        widget._move_to_widget.connect(self._move_to_wid)

        self.grid_layout.addWidget(widget, self.row, self.col, alignment=Qt.AlignmentFlag.AlignTop)
        Config.img_viewer_images[data["src"]] = widget

        self.col += 1
        if self.col >= self.clmn_count:
            self.col = 0
            self.row += 1

    def _reload_search(self, width: int):
        self.search_thread.stop_cmd()
        self.search_thread.wait()

        widgets = self.findChildren(Thumbnail)
        for i in widgets:
            i.hide()

        self.clmn_count = width // Config.thumb_size
        if self.clmn_count < 1:
            self.clmn_count = 1
        self.row, self.col = 0, 0

        self.search_thread = SearchFinderThread(Config.json_data["root"], self.search_text)
        self.search_thread._new_widget.connect(self._add_new_widget)
        self.search_thread._finished.connect(self.search_finished.emit)
        self.search_thread.start()

    def _rearrange_already_search(self, width: int):
        widgets = self.findChildren(Thumbnail)
        
        self.clmn_count = width // Config.thumb_size
        if self.clmn_count < 1:
            self.clmn_count = 1
        self.row, self.col = 0, 0

        for wid in widgets:
            self.grid_layout.addWidget(wid, self.row, self.col)
            self.col += 1
            if self.col >= self.clmn_count:
                self.col = 0
                self.row += 1

    def _move_to_wid(self, src: str):
        try:
            wid: Thumbnail = Config.img_viewer_images[src]
            wid.setFrameShape(QFrame.Shape.Panel)
            self.ensureWidgetVisible(wid)
            QTimer.singleShot(1000, lambda: self._set_no_frame(wid))
        except (RuntimeError, KeyError) as e:
            print("move to wid error: ", e)

    def _set_no_frame(self, wid: Thumbnail):
        try:
            wid.setFrameShape(QFrame.Shape.NoFrame)
        except (RuntimeError):
            pass

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        try:
            self.search_thread.disconnect()
        except TypeError:
            pass
        self.search_thread.stop_cmd()
        return super().closeEvent(a0)
    

class GridSearch(GridSearchBase):
    def __init__(self, width: int, search_text: str):
        super().__init__(width, search_text)

    def rearrange(self, width: int):
        if self.search_thread.isRunning():
            self._rearrange_already_search(width)

    def stop_and_wait_threads(self):
        self.search_thread.stop_cmd()
        self.search_thread.wait()