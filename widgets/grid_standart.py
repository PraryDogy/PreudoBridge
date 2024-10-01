import os
import subprocess

import numpy as np
import sqlalchemy
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QContextMenuEvent, QMouseEvent, QPixmap
from PyQt5.QtWidgets import (QAction, QFrame, QGridLayout, QLabel, QMenu,
                             QSizePolicy, QSpacerItem, QVBoxLayout, QWidget)

from cfg import Config
from database import Cache, Dbase
from fit_img import FitImg
from utils import Utils

from .grid_base import GridBase
from .image_viewer import WinImageView


class GridStandartStorage:
    load_images_threads: list = []


class LoadImagesThread(QThread):
    stop_thread = pyqtSignal()
    finished_thread = pyqtSignal()
    
    def __init__(self, finder_images: dict[tuple: QLabel]):
        super().__init__()

        self.finder_images: dict[tuple: QLabel] = finder_images # (src, size, modified): QLabel
        self.remove_db_images: dict[tuple: str] = {}

        self.db_images: dict = {}
        
        self.flag = True
        self.stop_thread.connect(self.stop_thread_cmd)

        self.session = Dbase.get_session()

    def run(self):
        # print(self, "thread started")
        self.db_images: dict = self.get_db_images()
        self.load_already_images()
        self.create_new_images(images=self.finder_images)
        self.remove_images()
        self.session.commit()
        self.session.close()
        self.finished_thread.emit()
        # print(self, "thread finished")

    def create_new_images(self, images: dict):
        images_copy = images.copy()

        for (src, size, modified), widget in images_copy.items():
            if not self.flag:
                break

            if os.path.isdir(src):
                continue

            img = Utils.read_image(src)
            img = FitImg.start(img, Config.thumb_size)

            try:
                self.set_new_image(widget, img)
            except AttributeError as e:
                pass

            try:
                img = Utils.image_array_to_bytes(img)
                q = sqlalchemy.insert(Cache)
                q = q.values({
                    "img": img,
                    "src": src,
                    "size": size,
                    "modified": modified
                    })
                self.session.execute(q)
            except Exception as e:
                # print(e)
                pass

    def load_already_images(self):
        for (src, size, modified), bytearray_image in self.db_images.items():
            widget: QLabel = self.finder_images.get((src, size, modified))

            if not self.flag:
                break

            if widget:
                pixmap: QPixmap = Utils.pixmap_from_bytes(bytearray_image)
                widget.setPixmap(pixmap)
                self.finder_images.pop((src, size, modified))
            else:
                self.remove_db_images[(src, size, modified)] = ""

    def remove_images(self):
        for (src, _, _), _ in self.remove_db_images.items():
            q = sqlalchemy.delete(Cache)
            q = q.where(Cache.src==src)
            self.session.execute(q)

    def get_db_images(self):
        q = sqlalchemy.select(Cache.img, Cache.src, Cache.size, Cache.modified)
        q = q.where(Cache.src.contains(Config.json_data["root"]))
        res = self.session.execute(q).fetchall()
        return {
            (src, size, modified): img
            for img, src, size,  modified in res
            }

    def stop_thread_cmd(self):
        self.flag = False

    def set_new_image(self, widget: QLabel, image: np.ndarray):
        pixmap = Utils.pixmap_from_array(image)
        try:
            widget.setPixmap(pixmap)
        except RuntimeError:
            pass


class LoadFinderItems:
    def __init__(self):
        super().__init__()
        self.finder_items: dict = {}

    def get(self):
        try:
            self.__get_items()
            self.__sort_items()
        except (PermissionError, FileNotFoundError):
            self.finder_items: dict = {}
        
        return self.finder_items

    def __get_items(self):
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
            
    def __sort_items(self):
        sort_data = {"name": 1, "size": 2,  "modify": 3, "type": 4}
        # начинаем с 1, потому что 0 у нас src, нам не нужна сортировка по src

        index = sort_data.get(Config.json_data["sort"])
        self.finder_items = dict(
            sorted(self.finder_items.items(), key=lambda item: item[0][index])
            )

        if Config.json_data["reversed"]:
            self.finder_items = dict(reversed(self.finder_items.items()))


class NameLabel(QLabel):
    def __init__(self, filename: str):
        super().__init__()
        self.setText(self.split_text(filename))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def split_text(self, text: str) -> list[str]:
        max_length = 27
        lines = []
        
        while len(text) > max_length:
            lines.append(text[:max_length])
            text = text[max_length:]

        if text:
            lines.append(text)

        if len(lines) > 2:
            lines = lines[:2]
            lines[-1] = lines[-1][:max_length-3] + '...'

        return "\n".join(lines)


class Thumbnail(QFrame):
    img_view_closed = pyqtSignal(str)

    def __init__(self, filename: str, src: str):
        super().__init__()
        self.setFixedSize(250, 300)
        self.src = src

        self.setFrameShape(QFrame.Shape.NoFrame)
        tooltip = filename + "\n" + src
        self.setToolTip(tooltip)

        v_lay = QVBoxLayout()
        self.setLayout(v_lay)

        self.img_label = QLabel()
        self.img_label.setFixedHeight(Config.thumb_size)
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_lay.addWidget(self.img_label)

        filename = os.path.basename(src)
        img_name = NameLabel(filename)
        v_lay.addWidget(img_name)

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        self.setFrameShape(QFrame.Shape.Panel)
        QTimer.singleShot(500, lambda: self.setFrameShape(QFrame.Shape.NoFrame))
        self.win = WinImageView(self, self.src)
        Utils.center_win(parent=Utils.get_main_win(), child=self.win)
        self.win.closed.connect(lambda src: self.img_view_closed.emit(src))
        self.win.show()

        return super().mouseReleaseEvent(a0)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:

        self.setFrameShape(QFrame.Shape.Panel)

        context_menu = QMenu(self)

        # Пункт "Просмотр"
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

        context_menu.exec_(self.mapToGlobal(a0.pos()))

        self.setFrameShape(QFrame.Shape.NoFrame)

        return super().contextMenuEvent(a0)

    def view_file(self):
        if self.src.endswith(Config.img_ext):
            self.win = WinImageView(self, self.src)
            self.win.closed.connect(lambda src: self.img_view_closed.emit(src))
            main_win = Utils.get_main_win()
            Utils.center_win(parent=main_win, child=self.win)
            self.win.show()

    def open_default(self):
        subprocess.call(["open", self.src])

    def show_in_finder(self):
        subprocess.call(["open", "-R", self.src])


class GridStandart(GridBase):
    def __init__(self, width: int):
        super().__init__()
        self.setWidgetResizable(True)

        Config.img_viewer_images.clear()
        self.finder_images: dict = {}
        clmn_count = width // Config.thumb_size
        if clmn_count < 1:
            clmn_count = 1

        main_wid = QWidget()
        self.grid_layout = QGridLayout(main_wid)
        self.grid_layout.setSpacing(5)
        self.setWidget(main_wid)

        row, col = 0, 0

        finder_items = LoadFinderItems()
        finder_items = finder_items.get()

        for (src, filename, size, modified, _), _ in finder_items.items():
            thumbnail = Thumbnail(filename, src)
            thumbnail.img_view_closed.connect(lambda src: self.move_to_wid(src))
            self.set_default_image(thumbnail.img_label, "images/file_210.png")

            self.grid_layout.addWidget(thumbnail, row, col)

            col += 1
            if col >= clmn_count:
                col = 0
                row += 1

            self.finder_images[(src, size, modified)] = thumbnail.img_label
            Config.img_viewer_images[src] = thumbnail

        if self.finder_images:
            row_spacer = QSpacerItem(1, 1, QSizePolicy.Minimum, QSizePolicy.Expanding)
            self.grid_layout.addItem(row_spacer, row + 1, 0)
            clmn_spacer = QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum)
            self.grid_layout.addItem(clmn_spacer, 0, clmn_count + 1)
            self.start_load_images_thread()

        else:
            no_images = QLabel(f"{Config.json_data['root']}\nНет изображений")
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0, Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setColumnStretch(0, 1)
            self.grid_layout.setRowStretch(0, 1)

    def set_default_image(self, widget: QLabel, png_path: str):
        pixmap = QPixmap(png_path)
        try:
            widget.setPixmap(pixmap)
        except RuntimeError:
            pass

    def move_to_wid(self, src: str):
        try:
            wid: Thumbnail = Config.img_viewer_images[src]
            wid.setFrameShape(QFrame.Shape.Panel)
            self.ensureWidgetVisible(wid)
            QTimer.singleShot(1000, lambda: self.set_no_frame(wid))
        except (RuntimeError, KeyError) as e:
            print(e)

    def set_no_frame(self, wid: Thumbnail):
        try:
            wid.setFrameShape(QFrame.Shape.NoFrame)
        except (RuntimeError):
            pass

    def stop_and_wait_threads(self):
        for i in GridStandartStorage.load_images_threads:
            i: LoadImagesThread
            i.stop_thread.emit()

            if i.isFinished():
                GridStandartStorage.load_images_threads.remove(i)

    def stop_threads(self):
        for thread in GridStandartStorage.load_images_threads:
            thread: LoadImagesThread
            thread.stop_thread.emit()
            thread.wait()

    def start_load_images_thread(self):
        new_thread = LoadImagesThread(self.finder_images)
        GridStandartStorage.load_images_threads.append(new_thread)
        new_thread.start()

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self.stop_threads()
        return super().closeEvent(a0)