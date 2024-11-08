import os
import subprocess

import sqlalchemy
from PyQt5.QtCore import QEvent, QPoint, QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import (QCloseEvent, QContextMenuEvent, QKeyEvent,
                         QMouseEvent, QPainter, QPaintEvent, QPixmap,
                         QResizeEvent)
from PyQt5.QtWidgets import (QAction, QFrame, QHBoxLayout, QLabel, QMenu,
                             QSpacerItem, QVBoxLayout, QWidget)

from cfg import COLORS, IMAGE_APPS, STAR_SYM, JsonData
from database import CACHE, Dbase
from signals import SignalsApp
from utils import Utils

from ._base import WinBase
from ._grid import Thumb
from ._svg_widgets import SvgShadowed
from .win_info import WinInfo


class Shared:
    loaded_images: dict[str, QPixmap] = {}
    threads: list[QThread] = []


class ImageData:
    __slots__ = ["src", "width", "pixmap"]
    
    def __init__(self, src: str, width: int, pixmap: QPixmap):
        self.src: str = src
        self.width: int = width
        self.pixmap: QPixmap = pixmap


class LoadImageThread(QThread):
    _finished = pyqtSignal(ImageData)

    def __init__(self, img_src: str):
        super().__init__(parent=None)
        self.img_src: str = img_src

    def run(self):
        if self.img_src not in Shared.loaded_images:
            img_array = Utils.read_image(self.img_src)
            if img_array is not NotImplemented:
                pixmap = Utils.pixmap_from_array(img_array)
                Shared.loaded_images[self.img_src] = pixmap
            else:
                pixmap = QPixmap("images/file_1024.png")
        else:
            pixmap = Shared.loaded_images.get(self.img_src)

        if len(Shared.loaded_images) > 50:
            first_img = list(Shared.loaded_images.keys())[0]
            Shared.loaded_images.pop(first_img)

        if isinstance(pixmap, QPixmap):
            self._finished.emit(ImageData(self.img_src, pixmap.width(), pixmap))
        else:
            self._finished.emit(ImageData(self.img_src, 0, None))


class ImageWidget(QLabel):
    mouse_moved = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMouseTracking(True)

        self.current_pixmap: QPixmap = None
        self.scale_factor: float = 1.0
        self.offset = QPoint(0, 0)
        self.w, self.h = 0, 0

    def set_image(self, pixmap: QPixmap):
        self.current_pixmap = pixmap
        self.scale_factor = 1.0
        self.offset = QPoint(0, 0)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.w, self.h = self.width(), self.height()

        self.current_pixmap.scaled(
            self.w, self.h, 
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
            )
        self.update()

    def zoom_in(self):
        self.scale_factor *= 1.1
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.update()

    def zoom_out(self):
        self.scale_factor /= 1.1
        self.update()

    def zoom_reset(self):
        self.scale_factor = 1.0
        self.offset = QPoint(0, 0)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    def mousePressEvent(self, ev: QMouseEvent | None) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self.last_mouse_pos = ev.pos()
        # return super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev: QMouseEvent | None) -> None:
        self.mouse_moved.emit()
        if ev.buttons() == Qt.MouseButton.LeftButton and self.scale_factor > 1.0:
            delta = ev.pos() - self.last_mouse_pos
            self.offset += delta
            self.last_mouse_pos = ev.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.update()
        # return super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev: QMouseEvent | None) -> None:
        if self.scale_factor > 1.0:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        # return super().mouseReleaseEvent(ev)

    def paintEvent(self, a0: QPaintEvent | None) -> None:
        if self.current_pixmap is not None:
            painter = QPainter(self)
            scaled_pixmap = self.current_pixmap.scaled(
                int(self.w * self.scale_factor),
                int(self.h * self.scale_factor),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
                )

            offset = self.offset + QPoint(
                int((self.width() - scaled_pixmap.width()) / 2),
                int((self.height() - scaled_pixmap.height()) / 2)
                )
            painter.drawPixmap(offset, scaled_pixmap)
        # return super().paintEvent(a0)

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        self.w, self.h = self.width(), self.height()
        self.update()
        # return super().resizeEvent(a0)


class ZoomBtns(QFrame):
    press_close = pyqtSignal()
    zoomed_in = pyqtSignal()
    zoomed_out = pyqtSignal()
    zoomed_fit = pyqtSignal()

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            """
            background-color: rgba(128, 128, 128, 0.40);
            border-radius: 15px;
            """
            )

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(h_layout)

        h_layout.addSpacerItem(QSpacerItem(5, 0))

        self.zoom_out = SvgShadowed(os.path.join("images", "zoom_out.svg"), 45)
        self.zoom_out.mouseReleaseEvent = lambda e: self.zoomed_out.emit()
        h_layout.addWidget(self.zoom_out)
        h_layout.addSpacerItem(QSpacerItem(10, 0))

        self.zoom_in = SvgShadowed(os.path.join("images", "zoom_in.svg"), 45)
        self.zoom_in.mouseReleaseEvent = lambda e: self.zoomed_in.emit()
        h_layout.addWidget(self.zoom_in)
        h_layout.addSpacerItem(QSpacerItem(10, 0))

        self.zoom_fit = SvgShadowed(os.path.join("images", "zoom_fit.svg"), 45)
        self.zoom_fit.mouseReleaseEvent = lambda e: self.zoomed_fit.emit()
        h_layout.addWidget(self.zoom_fit)
        h_layout.addSpacerItem(QSpacerItem(10, 0))

        self.zoom_close = SvgShadowed(os.path.join("images", "zoom_close.svg"), 45)
        self.zoom_close.mouseReleaseEvent = lambda e: self.press_close.emit()
        h_layout.addWidget(self.zoom_close)

        h_layout.addSpacerItem(QSpacerItem(5, 0))

        self.adjustSize()


class SwitchImageBtn(QFrame):
    pressed = pyqtSignal()

    def __init__(self, icon_name: str, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            """
            background-color: rgba(128, 128, 128, 0.40);
            border-radius: 27px;
            """
            )
        self.setFixedSize(54, 54)

        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(v_layout)

        btn = SvgShadowed(os.path.join("images", icon_name), 50)
        v_layout.addWidget(btn)

        self.mouseReleaseEvent = lambda e: self.pressed.emit()


class PrevImageBtn(SwitchImageBtn):
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__("prev.svg", parent)


class NextImageBtn(SwitchImageBtn):
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__("next.svg", parent)


class WinImgView(WinBase):
    def __init__(self, src: str, path_to_wid: dict[str, Thumb]):
        super().__init__()
        self.src: str = src

        self.wid: Thumb = path_to_wid.get(src)

        self.path_to_wid: dict[str, Thumb] = {
            path: wid
            for path, wid in path_to_wid.items()
            if not wid.must_hidden
            }

        self.image_paths: list = [
            i for i in self.path_to_wid.keys()
            if os.path.isfile(i)
            ]

        self.setMinimumSize(QSize(400, 300))
        self.resize(JsonData.ww_im, JsonData.hh_im)
        self.setObjectName("img_view")
        self.setStyleSheet("""#img_view {background: black;}""")
        self.setMouseTracking(True)
        self.installEventFilter(self)

        self.v_layout = QVBoxLayout()
        self.v_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.v_layout)

        self.mouse_move_timer = QTimer(self)
        self.mouse_move_timer.setSingleShot(True)
        self.mouse_move_timer.timeout.connect(self.hide_all_buttons)

        self.img_label = ImageWidget()
        self.img_label.mouse_moved.connect(self.mouse_moved_cmd)
        self.v_layout.addWidget(self.img_label)

        self.prev_image_btn = PrevImageBtn(self)
        self.prev_image_btn.pressed.connect(lambda: self.switch_img_btn("-"))

        self.next_image_btn = NextImageBtn(self)
        self.next_image_btn.pressed.connect(lambda: self.switch_img_btn("+"))

        self.zoom_btns = ZoomBtns(parent=self)
        self.zoom_btns.zoomed_in.connect(self.img_label.zoom_in)
        self.zoom_btns.zoomed_out.connect(self.img_label.zoom_out)
        self.zoom_btns.zoomed_fit.connect(self.img_label.zoom_reset)
        self.zoom_btns.press_close.connect(self.close)

        self.hide_all_buttons()
        self.load_thumbnail()

# SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM

    def open_default(self, app_path: str):
        subprocess.call(["open", "-a", app_path, self.src])

    def show_in_finder(self):
        subprocess.call(["open", "-R", self.src])

    def set_title(self):
        t = ""
        if self.wid.rating > 0:
            t = STAR_SYM * self.wid.rating + " | "
        if self.wid.colors:
            t = t + self.wid.colors + " | "
        t = t + os.path.basename(self.src)

        self.setWindowTitle(t)

    def load_thumbnail(self):
        if self.src not in Shared.loaded_images:

            self.setWindowTitle("Загрузка")
            q = sqlalchemy.select(CACHE.c.hash).where(CACHE.c.src == self.src)

            with Dbase.engine.connect() as conn:
                hash = conn.execute(q).scalar() or None
                img = Utils.read_image_hash(hash)
                pixmap = Utils.pixmap_from_array(img)
                # if isinstance(thumbnail, bytes):
                #     pixmap = QPixmap()
                #     pixmap.loadFromData(thumbnail)
                # else:
                #     pixmap = QPixmap("images/file_1024.png")

                self.img_label.set_image(pixmap)

        self.load_image_thread()

    def load_image_thread(self):
        self.setWindowTitle("Загрузка")
        img_thread = LoadImageThread(self.src)
        Shared.threads.append(img_thread)
        img_thread._finished.connect(
            lambda image_data: self.load_image_finished(img_thread, image_data)
            )
        img_thread.start()

    def load_image_finished(self, thread: LoadImageThread, image_data: ImageData):
        if image_data.width == 0:
            return

        elif image_data.src != self.src:
            return
                        
        self.img_label.set_image(image_data.pixmap)
        self.set_title()
        Shared.threads.remove(thread)

# GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI

    def hide_all_buttons(self):
        for i in (self.prev_image_btn, self.next_image_btn, self.zoom_btns):
            if i.underMouse():
                return
        self.zoom_btns.hide()
        self.prev_image_btn.hide()
        self.next_image_btn.hide()

    def switch_img(self, offset: int):
        try:
            current_index: int = self.image_paths.index(self.src)
        except ValueError:
            current_index: int = 0

        total_images: int = len(self.image_paths)
        new_index: int = (current_index + offset) % total_images

        self.src: str = self.image_paths[new_index]
        self.wid: Thumb = self.path_to_wid.get(self.src)
        SignalsApp.all.move_to_wid.emit(self.wid)
        self.load_thumbnail()

    def switch_img_btn(self, flag: str) -> None:
        if flag == "+":
            self.switch_img(1)
        else:
            self.switch_img(-1)
        self.img_label.setCursor(Qt.CursorShape.ArrowCursor)

    def mouse_moved_cmd(self):
        self.mouse_move_timer.stop()
        self.prev_image_btn.show()
        self.next_image_btn.show()
        self.zoom_btns.show()
        self.mouse_move_timer.start(2000)

    def color_click(self, menu: QMenu, colors: str):
        self.wid.color_click(menu, colors)
        self.set_title()

    def rating_click(self, menu: QMenu, wid: QAction, rate: int):
        self.wid.rating_click(menu, wid, rate)
        self.set_title()

    def show_info_win(self):
        self.win_info = WinInfo(self.wid.get_info())
        Utils.center_win(parent=self, child=self.win_info)
        self.win_info.show()

# EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS 

    def keyPressEvent(self, ev: QKeyEvent | None) -> None:
        if ev.key() == Qt.Key.Key_Left:
            self.switch_img(-1)

        elif ev.key() == Qt.Key.Key_Right:
            self.switch_img(1)

        elif ev.key() == Qt.Key.Key_Escape:
            self.close()

        elif ev.key() == Qt.Key.Key_Equal:
            self.img_label.zoom_in()

        elif ev.key() == Qt.Key.Key_Minus:
            self.img_label.zoom_out()

        elif ev.key() == Qt.Key.Key_0:
            self.img_label.zoom_reset()

        elif ev.key() == Qt.Key.Key_Space:
            self.close()

        elif ev.modifiers() & Qt.KeyboardModifier.ControlModifier and ev.key() == Qt.Key.Key_I:
            self.wid.show_info_win()

        return super().keyPressEvent(ev)

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        vertical_center = a0.size().height() // 2 - self.next_image_btn.height() // 2
        right_window_side = a0.size().width() - self.next_image_btn.width()
        self.prev_image_btn.move(30, vertical_center)
        self.next_image_btn.move(right_window_side - 30, vertical_center)

        horizontal_center = a0.size().width() // 2 - self.zoom_btns.width() // 2
        bottom_window_side = a0.size().height() - self.zoom_btns.height()
        self.zoom_btns.move(horizontal_center, bottom_window_side - 30)

        JsonData.ww_im = self.width()
        JsonData.hh_im = self.height()

    def leaveEvent(self, a0: QEvent | None) -> None:
        self.hide_all_buttons()

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        Shared.loaded_images.clear()

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        context_menu = QMenu(self)

        open_menu = QMenu("Открыть в приложении", self)
        context_menu.addMenu(open_menu)

        for name, app_path in IMAGE_APPS.items():
            wid = QAction(name, parent=open_menu)
            wid.triggered.connect(lambda e, a=app_path: self.open_default(a))
            open_menu.addAction(wid)

        context_menu.addSeparator()

        info = QAction("Инфо", self)
        info.triggered.connect(self.show_info_win)
        context_menu.addAction(info)

        show_in_finder_action = QAction("Показать в Finder", self)
        show_in_finder_action.triggered.connect(self.show_in_finder)
        context_menu.addAction(show_in_finder_action)

        copy_path = QAction("Скопировать путь до файла", self)
        copy_path.triggered.connect(lambda: Utils.copy_path(self.src))
        context_menu.addAction(copy_path)

        context_menu.addSeparator()

        color_menu = QMenu("Цвета", self)
        context_menu.addMenu(color_menu)

        for color, text in COLORS.items():
            wid = QAction(parent=color_menu, text=f"{color} {text}")
            wid.setCheckable(True)

            if color in self.wid.colors:
                wid.setChecked(True)

            wid.triggered.connect(lambda e, c=color: self.color_click(color_menu, c))
            color_menu.addAction(wid)

        rating_menu = QMenu("Рейтинг", self)
        context_menu.addMenu(rating_menu)

        for rate in range(1, 6):
            wid = QAction(parent=rating_menu, text=STAR_SYM * rate)
            wid.setCheckable(True)

            if self.wid.rating == rate:
                wid.setChecked(True)

            wid.triggered.connect(lambda e, w=wid, r=rate: self.rating_click(rating_menu, w, r))
            rating_menu.addAction(wid)

        context_menu.exec_(self.mapToGlobal(a0.pos()))


class WinImgViewSingle(WinBase):
    def __init__(self, src: str):
        super().__init__()
        self.src: str = src

        self.setMinimumSize(QSize(400, 300))
        self.resize(JsonData.ww_im, JsonData.hh_im)
        self.setObjectName("img_view")
        self.setStyleSheet("""#img_view {background: black;}""")
        self.setMouseTracking(True)
        self.installEventFilter(self)

        self.v_layout = QVBoxLayout()
        self.v_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.v_layout)

        self.mouse_move_timer = QTimer(self)
        self.mouse_move_timer.setSingleShot(True)
        self.mouse_move_timer.timeout.connect(self.hide_all_buttons)

        self.img_label = ImageWidget()
        self.img_label.mouse_moved.connect(self.mouse_moved_cmd)
        self.v_layout.addWidget(self.img_label)

        self.zoom_btns = ZoomBtns(parent=self)
        self.zoom_btns.zoomed_in.connect(self.img_label.zoom_in)
        self.zoom_btns.zoomed_out.connect(self.img_label.zoom_out)
        self.zoom_btns.zoomed_fit.connect(self.img_label.zoom_reset)
        self.zoom_btns.press_close.connect(self.close)

        self.hide_all_buttons()
        self.load_thumbnail()

# SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM

    def open_default(self, app_path: str):
        subprocess.call(["open", "-a", app_path, self.src])

    def show_in_finder(self):
        subprocess.call(["open", "-R", self.src])

    def load_thumbnail(self):
        if self.src not in Shared.loaded_images:

            self.setWindowTitle("Загрузка")
            q = sqlalchemy.select(CACHE.c.img).filter(CACHE.c.src == self.src)

            with Dbase.engine.connect() as conn:
                thumbnail = conn.execute(q).scalar() or None
                if isinstance(thumbnail, bytes):
                    pixmap = QPixmap()
                    pixmap.loadFromData(thumbnail)
                else:
                    pixmap = QPixmap("images/file_1024.png")

                self.img_label.set_image(pixmap)

        self.load_image_thread()

    def load_image_thread(self):
        self.setWindowTitle("Загрузка")
        img_thread = LoadImageThread(self.src)
        Shared.threads.append(img_thread)
        img_thread._finished.connect(
            lambda image_data: self.load_image_finished(img_thread, image_data)
            )
        img_thread.start()

    def load_image_finished(self, thread: LoadImageThread, image_data: ImageData):
        if image_data.width == 0:
            return

        elif image_data.src != self.src:
            return
                        
        self.img_label.set_image(image_data.pixmap)
        name = os.path.basename(image_data.src)
        self.setWindowTitle(name)
        Shared.threads.remove(thread)

# GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI

    def hide_all_buttons(self):
        if self.zoom_btns.underMouse():
            return
        self.zoom_btns.hide()

    def mouse_moved_cmd(self):
        self.mouse_move_timer.stop()
        self.zoom_btns.show()
        self.mouse_move_timer.start(2000)

    def show_info_win(self):
        return
        self.win_info = WinInfo(self.wid.get_info())
        Utils.center_win(parent=self, child=self.win_info)
        self.win_info.show()

# EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS 

    def keyPressEvent(self, ev: QKeyEvent | None) -> None:
        if ev.key() == Qt.Key.Key_Escape:
            self.close()

        elif ev.key() == Qt.Key.Key_Equal:
            self.img_label.zoom_in()

        elif ev.key() == Qt.Key.Key_Minus:
            self.img_label.zoom_out()

        elif ev.key() == Qt.Key.Key_0:
            self.img_label.zoom_reset()

        elif ev.key() == Qt.Key.Key_Space:
            self.close()

        # elif ev.modifiers() & Qt.KeyboardModifier.ControlModifier and ev.key() == Qt.Key.Key_I:
            # self.wid.show_info_win()

        return super().keyPressEvent(ev)

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        horizontal_center = a0.size().width() // 2 - self.zoom_btns.width() // 2
        bottom_window_side = a0.size().height() - self.zoom_btns.height()
        self.zoom_btns.move(horizontal_center, bottom_window_side - 30)

        JsonData.ww_im = self.width()
        JsonData.hh_im = self.height()

    def leaveEvent(self, a0: QEvent | None) -> None:
        self.hide_all_buttons()

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        Shared.loaded_images.clear()

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        context_menu = QMenu(self)

        open_menu = QMenu("Открыть в приложении", self)
        context_menu.addMenu(open_menu)

        for name, app_path in IMAGE_APPS.items():
            wid = QAction(name, parent=open_menu)
            wid.triggered.connect(lambda e, a=app_path: self.open_default(a))
            open_menu.addAction(wid)

        context_menu.addSeparator()

        info = QAction("Инфо", self)
        info.triggered.connect(self.show_info_win)
        context_menu.addAction(info)

        show_in_finder_action = QAction("Показать в Finder", self)
        show_in_finder_action.triggered.connect(self.show_in_finder)
        context_menu.addAction(show_in_finder_action)

        copy_path = QAction("Скопировать путь до файла", self)
        copy_path.triggered.connect(lambda: Utils.copy_path(self.src))
        context_menu.addAction(copy_path)

        context_menu.exec_(self.mapToGlobal(a0.pos()))
    