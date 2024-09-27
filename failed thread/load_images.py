import io
import json
import logging
import os
import subprocess
import sys
from functools import partial

import cv2
import numpy as np
import psd_tools
import sqlalchemy
import tifffile
from PIL import Image
from PyQt5.QtCore import (QByteArray, QDir, QEvent, QObject, QPoint, Qt,
                          QThread, QTimer, pyqtSignal)
from PyQt5.QtGui import QCloseEvent, QImage, QKeyEvent, QMouseEvent, QPixmap
from PyQt5.QtWidgets import (QAction, QApplication, QFileSystemModel, QFrame,
                             QGridLayout, QHBoxLayout, QLabel, QMenu,
                             QMessageBox, QPushButton, QScrollArea,
                             QSizePolicy, QSpacerItem, QSplitter, QTabBar,
                             QTreeView, QVBoxLayout, QWidget)

from cfg import Config
from database import Cache, Dbase
from fit_img import FitImg
from utils import Utils

psd_tools.psd.tagged_blocks.warn = lambda *args, **kwargs: None
psd_logger = logging.getLogger("psd_tools")
psd_logger.setLevel(logging.CRITICAL)


class NameLabel(QLabel):
    def __init__(self, filename: str):
        super().__init__()

        max_row = 27

        if len(filename) >= max_row:
            cut_name = filename[:max_row]
            filename = cut_name + "..."

        self.setText(filename)


class Thumbnail(QFrame):
    double_click = pyqtSignal(str)

    def __init__(self, filename: str, src: str, thumb_size: int):
        super().__init__()
        self.src = src

        self.setFrameShape(QFrame.Shape.StyledPanel)
        tooltip = filename + "\n" + src
        self.setToolTip(tooltip)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.mouseDoubleClickEvent = lambda e: self.double_click.emit(src)

        v_lay = QVBoxLayout()
        self.setLayout(v_lay)

        self.img_label = QLabel()
        self.img_label.setFixedSize(thumb_size, thumb_size)
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_lay.addWidget(self.img_label)

        filename = os.path.basename(src)
        img_name = NameLabel(filename)
        v_lay.addWidget(img_name)

    def show_context_menu(self, pos: QPoint):
        self.setFrameShape(QFrame.Shape.Panel)

        context_menu = QMenu(self)

        # Пункт "Просмотр"
        view_action = QAction("Просмотр", self)
        view_action.triggered.connect(self.view_file)
        context_menu.addAction(view_action)

        # Пункт "Открыть в программе по умолчанию"
        open_action = QAction("Открыть в программе по умолчанию", self)
        open_action.triggered.connect(self.open_default)
        context_menu.addAction(open_action)

        # Сепаратор
        context_menu.addSeparator()

        # Пункт "Показать в Finder"
        show_in_finder_action = QAction("Показать в Finder", self)
        show_in_finder_action.triggered.connect(self.show_in_finder)
        context_menu.addAction(show_in_finder_action)

        # Отображаем меню
        context_menu.exec_(self.mapToGlobal(pos))

        self.setFrameShape(QFrame.Shape.StyledPanel)

    def view_file(self):
        QMessageBox.information(self, "Просмотр", f"Просмотр файла: {self.src}")

    def open_default(self):
        subprocess.call(["open", self.src])

    def show_in_finder(self):
        subprocess.call(["open", "-R", self.src])


class PixmapFromBytes(QPixmap):
    def __init__(self, byte_array: QByteArray) -> QPixmap:
        super().__init__()

        ba = QByteArray(byte_array)
        self.loadFromData(ba, "JPEG")


class DbImage(io.BytesIO):
    def __init__(self, image: np.ndarray) -> io.BytesIO:
        super().__init__()
        img = np.array(image)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        res, buffer = cv2.imencode(".jpeg", img)
        self.write(buffer)


class ImgUtils:

    @staticmethod
    def read_tiff(src: str) -> np.ndarray:
        try:
            img = tifffile.imread(files=src)[:,:,:3]
            if str(object=img.dtype) != "uint8":
                img = (img/256).astype(dtype="uint8")
            return img
        except Exception as e:
            print("tifffle error:", e, src)
            return None

    @staticmethod
    def read_psd(src: str) -> np.ndarray:
        try:
            img = psd_tools.PSDImage.open(fp=src)
            print("image opened")
            img = img.composite()
            print("image composited")

            if img.mode == 'RGBA':
                img = img.convert('RGB')
            
            img = np.array(img)
            return img

        except Exception as e:
            print("psd tools error:", e, src)
            return None
            
    @staticmethod
    def read_jpg(path: str) -> np.ndarray:
        image = cv2.imread(path, cv2.IMREAD_UNCHANGED)  # Чтение с альфа-каналом
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        if image is None:
            print("Ошибка загрузки изображения")
            return None

        return image
        
    @staticmethod
    def read_png(path: str) -> Image.Image:
        image = cv2.imread(path, cv2.IMREAD_UNCHANGED)  # Чтение с альфа-каналом

        if image is None:
            return None

        if image.shape[2] == 4:
            alpha_channel = image[:, :, 3] / 255.0
            rgb_channels = image[:, :, :3]
            background_color = np.array([255, 255, 255], dtype=np.uint8)
            background = np.full(rgb_channels.shape, background_color, dtype=np.uint8)
            converted = (rgb_channels * alpha_channel[:, :, np.newaxis] + background * (1 - alpha_channel[:, :, np.newaxis])).astype(np.uint8)
        else:
            converted = image

        return converted


class LoadImages(QObject):
    stop_load_images = pyqtSignal()

    def __init__(self, widgets_grid: dict[tuple: QLabel]):
        super().__init__()

        self.widgets_grid: dict[tuple: QLabel] = widgets_grid # (src, size, modified): QLabel
        self.remove_db_images: dict[tuple: str] = {}
        first_img = next(iter(self.widgets_grid))[0]
        self.root = os.path.dirname(first_img)

        self.db_images: dict = {}

        self.flag = True
        self.stop_load_images.connect(self.stop_cmd)

        self.session = Dbase.get_session()

    def run(self):
        print(self, "thread started")
        self.db_images: dict = self.get_db_images()
        self.load_already_images()
        self.create_new_images(images=self.widgets_grid)
        self.remove_images()
        self.session.commit()
        self.session.close()
        self.finished_thread.emit()
        print(self, "thread finished")

    def create_new_images(self, images: dict):
        images_copy = images.copy()

        for (src, size, modified), widget in images_copy.items():
            img = None
            src_lower: str = src.lower()

            if not self.flag:
                break

            if os.path.isdir(src):
                continue

            elif src_lower.endswith((".psd", ".psb")):
                img = ImgUtils.read_psd(src)
                img = FitImg.start(img, Config.thumb_size)

            elif src_lower.endswith((".tiff", ".tif")):
                img = ImgUtils.read_tiff(src)
                img = FitImg.start(img, Config.thumb_size)

            elif src_lower.endswith((".jpg", ".jpeg")):
                img = ImgUtils.read_jpg(src)
                img = FitImg.start(img, Config.thumb_size)

            elif src_lower.endswith((".png")):
                img = ImgUtils.read_png(src)
                img = FitImg.start(img, Config.thumb_size)

            else:
                img = None

            try:
                self.set_new_image(widget, img)
            except AttributeError as e:
                pass

            try:
                img = DbImage(img).getvalue()
                q = sqlalchemy.insert(Cache)
                q = q.values({
                    "img": img,
                    "src": src,
                    "root": self.root,
                    "size": size,
                    "modified": modified
                    })
                self.session.execute(q)
            except Exception as e:
                pass

    def load_already_images(self):
        for (src, size, modified), bytearray_image in self.db_images.items():
            widget: QLabel = self.widgets_grid.get((src, size, modified))

            if not self.flag:
                break

            if widget:
                pixmap: QPixmap = PixmapFromBytes(bytearray_image)
                widget.setPixmap(pixmap)
                self.widgets_grid.pop((src, size, modified))
            else:
                self.remove_db_images[(src, size, modified)] = ""

    def remove_images(self):
        for (src, size, modified), string in self.remove_db_images.items():
            q = sqlalchemy.delete(Cache)
            q = q.where(Cache.src==src, Cache.size==size, Cache.modified==modified)
            self.session.execute(q)

    def get_db_images(self):
        q = sqlalchemy.select(Cache.img, Cache.src, Cache.size, Cache.modified)
        q = q.where(Cache.root==self.root)
        res = self.session.execute(q).fetchall()
        return {
            (src, size, modified): img
            for img, src, size,  modified in res
            }

    def stop_cmd(self):
        self.flag = False

    def set_new_image(self, widget: QLabel, image: np.ndarray):
        "input nd array RGB"
        height, width, channel = image.shape
        bytes_per_line = channel * width
        qimage = QImage(image.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)

        qimage = QPixmap.fromImage(qimage)

        try:
            widget.setPixmap(qimage)
        except RuntimeError:
            pass


class WidgetsGrid(QObject):
    on_wid_double_clicked = pyqtSignal(str)
    stop_widgets_grid = pyqtSignal()

    def __init__(self, grid: QGridLayout, path: str, clmn_count: int):
        super().__init__()

        self.grid: QGridLayout = grid
        self.path = path
        self.clmn_count = clmn_count
        self.img_ext: tuple = (".jpg", "jpeg", ".tif", ".tiff", ".psd", ".psb", ".png")

        self.flag = True
        self.stop_widgets_grid.connect(self.stop_cmd)

    def run(self):
        self.widgets_grid: dict = {}

        self.finder_items = self.get_finder_items()

        if self.finder_items:
            self.sort_finder_items()
            self.create_widgets()

        return self.widgets_grid

    def get_finder_items(self):
        try:

            finder_items: dict = {}

            for item in os.listdir(self.path):
                src: str = os.path.join(self.path, item)

                if not self.flag:
                    break

                filename = src.split(os.sep)[-1]
                stats = os.stat(src)
                size = stats.st_size
                modified = stats.st_mtime
                filetype = os.path.splitext(filename)[1]

                if Config.json_data["only_photo"]:
                    if src.lower().endswith(self.img_ext):
                        finder_items[(src, filename, size, modified, filetype)] = None
                        continue
                else:
                    finder_items[(src, filename, size, modified, filetype)] = None

            return finder_items
                
        except PermissionError as e:
            return finder_items
        
    def sort_finder_items(self):
        sort_data = {"name": 1, "size": 2,  "modify": 3, "type": 4}
        # начинаем с 1, потому что 0 у нас src, нам не нужна сортировка по src

        index = sort_data.get(Config.json_data["sort"])
        self.finder_items = dict(
            sorted(self.finder_items.items(), key=lambda item: item[0][index])
            )

        if Config.json_data["reversed"]:
            self.finder_items = dict(reversed(self.finder_items.items()))

    def create_widgets(self):
        row, col = 0, 0

        for data, wid in self.finder_items.items():

            if not self.flag:
                break

            src, filename, size, modified, filetype = data

            thumbnail = Thumbnail(filename, src, Config.thumb_size)
            # thumbnail.double_click.connect(lambda: self.on_wid_double_clicked.emit(src))

            if os.path.isdir(src):
                self.set_default_image(thumbnail.img_label, "images/folder_210.png")
            else:
                self.set_default_image(thumbnail.img_label, "images/file_210.png")

            self.grid.addWidget(thumbnail, row, col)

            col += 1
            if col >= self.clmn_count:
                col = 0
                row += 1

            try:
                self.widgets_grid[(src, size, modified)] = thumbnail.img_label
            except FileNotFoundError as e:
                print(e, src)

        row_spacer = QSpacerItem(1, 1, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.grid.addItem(row_spacer, row + 1, 0)
        clmn_spacer = QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.grid.addItem(clmn_spacer, 0, self.clmn_count + 1)

    def set_default_image(self, widget: QLabel, png_path: str):
        pixmap = QPixmap(png_path)
        try:
            widget.setPixmap(pixmap)
        except RuntimeError:
            pass

    def stop_cmd(self):
        self.flag = False
        self.widgets_grid.clear()


class ImagesGridThread(QThread):
    stop_thread = pyqtSignal()

    def __init__(self, grid: QGridLayout, root: str, clmn_count: int):
        super().__init__()
        self.grid: QGridLayout = grid
        self.root: str = root
        self.clmn_count: int = clmn_count

    def run(self):
        widgets_grid = WidgetsGrid(self.grid, self.root, self.clmn_count)
        widgets_grid = widgets_grid.run()

        # if widgets_grid:
        #     load_images = LoadImages(widgets_grid)
        #     load_images.run()

    def stop_thread_cmd(self):
        ...