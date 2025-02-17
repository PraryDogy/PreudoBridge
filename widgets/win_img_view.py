import gc
import os

import sqlalchemy
from PyQt5.QtCore import QEvent, QObject, QPoint, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import (QCloseEvent, QColor, QContextMenuEvent, QKeyEvent,
                         QMouseEvent, QPainter, QPaintEvent, QPixmap,
                         QResizeEvent)
from PyQt5.QtWidgets import (QFrame, QHBoxLayout, QLabel, QSpacerItem,
                             QVBoxLayout, QWidget)

from cfg import Dynamic, JsonData, Static
from database import CACHE, Dbase
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from ._actions import CopyPath, Info, OpenInApp, RatingMenu, RevealInFinder
from ._base import OpenWin, UMenu, USvgWidget, WinBase
from ._grid import Thumb

KEY_RATING = {
    Qt.Key.Key_0: 0,
    Qt.Key.Key_1: 1,
    Qt.Key.Key_2: 2,
    Qt.Key.Key_3: 3,
    Qt.Key.Key_4: 4,
    Qt.Key.Key_5: 5
}


class ImageData:
    __slots__ = ["src", "width", "pixmap"]
    
    def __init__(self, src: str, pixmap: QPixmap):
        self.src: str = src
        self.pixmap: QPixmap = pixmap


class WorkerSignals(QObject):
    finished_ = pyqtSignal(ImageData)


class LoadThumbnail(URunnable):
    def __init__(self, src: str):
        super().__init__()
        self.signals_ = WorkerSignals()
        self.src = os.sep + src.strip(os.sep)
        self.name = os.path.basename(self.src)

    @URunnable.set_running_state
    def run(self):
        try:
            db = os.path.join(JsonData.root, Static.DB_FILENAME)
            dbase = Dbase()
            engine = dbase.create_engine(path=db)

            if engine is None:
                image_data = ImageData(src=self.src, pixmap=None)
                self.signals_.finished_.emit(image_data)
                return

            conn = engine.connect()

            q = sqlalchemy.select(CACHE.c.img)
            q = q.where(CACHE.c.name == Utils.hash_filename(filename=self.name))
            res = conn.execute(q).scalar() or None

            conn.close()

            if res is not None:
                img_array = Utils.bytes_to_array(res)
            else:
                img_array = None

            if img_array is None:
                pixmap = None

            else:
                pixmap = Utils.pixmap_from_array(img_array)

            image_data = ImageData(src=self.src, pixmap=pixmap)
            self.signals_.finished_.emit(image_data)

        except RuntimeError as e:
            Utils.print_error(parent=None, error=e)


class LoadImage(URunnable):
    cache: dict[str, QPixmap] = {}

    def __init__(self, src: str):
        super().__init__()
        self.signals_ = WorkerSignals()
        self.src: str = src

    @URunnable.set_running_state
    def run(self):
        try:
            if self.src not in self.cache:

                img_array = Utils.read_image(self.src)

                if img_array is None:
                    pixmap = None

                else:
                    pixmap = Utils.pixmap_from_array(img_array)
                    self.cache[self.src] = pixmap

                del img_array
                gc.collect()

            else:
                pixmap = self.cache.get(self.src)

            if len(self.cache) > 50:
                first_img = list(self.cache.keys())[0]
                self.cache.pop(first_img)

            image_data = ImageData(self.src, pixmap)

            self.signals_.finished_.emit(image_data)

        except RuntimeError as e:
            Utils.print_error(parent=None, error=e)


class ImageWidget(QLabel):
    mouse_moved = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMouseTracking(True)
        self.setStyleSheet("background: black;")

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
    cmd_close = pyqtSignal()
    cmd_in = pyqtSignal()
    cmd_out = pyqtSignal()
    cmd_fit = pyqtSignal()

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"""
            background-color: {Static.GRAY_UP_BTN};
            border-radius: 15px;
            """
            )

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(h_layout)

        h_layout.addSpacerItem(QSpacerItem(5, 0))

        self.zoom_out = USvgWidget(src=Static.ZOOM_OUT_SVG, size=45)
        self.zoom_out.mouseReleaseEvent = lambda e: self.cmd_out.emit()
        h_layout.addWidget(self.zoom_out)
        h_layout.addSpacerItem(QSpacerItem(10, 0))

        self.zoom_in = USvgWidget(src=Static.ZOOM_IN_SVG, size=45)
        self.zoom_in.mouseReleaseEvent = lambda e: self.cmd_in.emit()
        h_layout.addWidget(self.zoom_in)
        h_layout.addSpacerItem(QSpacerItem(10, 0))

        self.zoom_fit = USvgWidget(src=Static.ZOOM_FIT_SVG, size=45)
        self.zoom_fit.mouseReleaseEvent = lambda e: self.cmd_fit.emit()
        h_layout.addWidget(self.zoom_fit)
        h_layout.addSpacerItem(QSpacerItem(10, 0))

        self.zoom_close = USvgWidget(src=Static.CLOSE_SVG, size=45)
        self.zoom_close.mouseReleaseEvent = lambda e: self.cmd_close.emit()
        h_layout.addWidget(self.zoom_close)

        h_layout.addSpacerItem(QSpacerItem(5, 0))

        self.adjustSize()


class SwitchImageBtn(QFrame):
    pressed = pyqtSignal()

    def __init__(self, src: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(54, 54)

        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(v_layout)

        btn = USvgWidget(src=src, size=50)
        v_layout.addWidget(btn)

        self.mouseReleaseEvent = lambda e: self.pressed.emit()


class PrevImageBtn(SwitchImageBtn):
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(Static.PREV_SVG, parent=parent)


class NextImageBtn(SwitchImageBtn):
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(src=Static.NEXT_SVG, parent=parent)


class WinImgView(WinBase):
    task_count_limit = 10

    def __init__(self, src: str):
        super().__init__()
        self.setMinimumSize(QSize(400, 300))
        self.resize(Dynamic.ww_im, Dynamic.hh_im)

        self.task_count = 0
        self.src: str = src
        self.wid: Thumb = Thumb.path_to_wid.get(src)
        self.wid.text_changed.connect(self.set_title)
        self.path_to_wid: dict[str, Thumb] = {
            path: wid
            for path, wid in Thumb.path_to_wid.items()
            if not wid.must_hidden
            }
        self.image_paths: list = [
            i for i in self.path_to_wid.keys()
            if os.path.isfile(i)
            ]

        self.mouse_move_timer = QTimer(self)
        self.mouse_move_timer.setSingleShot(True)
        self.mouse_move_timer.timeout.connect(self.hide_btns)

        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(v_layout)

        self.img_label = ImageWidget()
        self.img_label.mouse_moved.connect(self.show_btns)
        v_layout.addWidget(self.img_label)

        self.prev_btn = PrevImageBtn(self)
        self.prev_btn.pressed.connect(lambda: self.switch_img_btn("-"))

        self.next_btn = NextImageBtn(self)
        self.next_btn.pressed.connect(lambda: self.switch_img_btn("+"))

        self.zoom_btns = ZoomBtns(parent=self)
        self.zoom_btns.cmd_in.connect(self.img_label.zoom_in)
        self.zoom_btns.cmd_out.connect(self.img_label.zoom_out)
        self.zoom_btns.cmd_fit.connect(self.img_label.zoom_reset)
        self.zoom_btns.cmd_close.connect(self.close)

        self.text_label = QLabel(parent=self.img_label)
        self.text_label.hide()

        self.hide_btns()
        self.load_thumbnail()

# SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM

    def set_title(self):
        t = ""
        if self.wid.rating > 0:
            t = Static.STAR_SYM * self.wid.rating + " | "
        t = t + os.path.basename(self.src)

        self.setWindowTitle(t)

    def load_thumbnail(self):
        self.text_label.hide()
        self.set_title()

        if self.src not in LoadImage.cache and not Dynamic.busy_db:

            self.task_ = LoadThumbnail(
                src=self.src
            )

            cmd_ = lambda image_data: self.load_thumbnail_finished(
                image_data=image_data
            )

            self.task_.signals_.finished_.connect(cmd_)

            UThreadPool.start(
                runnable=self.task_
            )

        else:
            self.show_text_label(text="Загрузка...")
            self.load_image()

    def show_text_label(self, text: str):
        pixmap = QPixmap(1, 1)
        pixmap.fill(QColor(0, 0, 0))
        self.img_label.set_image(pixmap)
        self.text_label.setText(text)
        self.text_label.show()

    def hide_text_label(self):
        self.text_label.hide()

    def load_thumbnail_finished(self, image_data: ImageData):

        if image_data.pixmap is None:
            self.show_text_label("Загрузка...")

        elif image_data.src == self.src:
            self.img_label.set_image(image_data.pixmap)

        self.load_image()

    def load_image(self):
        self.task_count += 1
        self.task_ = LoadImage(self.src)
        cmd_ = lambda image_data: self.load_image_finished(image_data)
        self.task_.signals_.finished_.connect(cmd_)
        UThreadPool.start(self.task_)

    def load_image_finished(self, image_data: ImageData):
        self.task_count -= 1
        self.hide_text_label()
        if image_data.pixmap is None:
            self.show_text_label("Ошибка чтения изображения.")
        elif image_data.src == self.src:
            self.img_label.set_image(image_data.pixmap)


# GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI

    def hide_btns(self):
        for i in (self.prev_btn, self.next_btn, self.zoom_btns):
            if i.underMouse():
                return
        self.zoom_btns.hide()
        self.prev_btn.hide()
        self.next_btn.hide()

    def switch_img(self, offset: int):
        if self.task_count == WinImgView.task_count_limit:
            return

        try:
            current_index: int = self.image_paths.index(self.src)
        except ValueError:
            current_index: int = 0

        total_images: int = len(self.image_paths)
        new_index: int = (current_index + offset) % total_images

        self.src: str = self.image_paths[new_index]

        self.wid.text_changed.disconnect()
        self.wid: Thumb = self.path_to_wid.get(self.src)
        self.wid.text_changed.connect(self.set_title)

        SignalsApp.instance.move_to_wid.emit(self.wid)
        self.load_thumbnail()

    def switch_img_btn(self, flag: str) -> None:
        if flag == "+":
            self.switch_img(1)
        else:
            self.switch_img(-1)
        self.img_label.setCursor(Qt.CursorShape.ArrowCursor)

    def show_btns(self):
        self.mouse_move_timer.stop()
        self.prev_btn.show()
        self.next_btn.show()
        self.zoom_btns.show()
        self.mouse_move_timer.start(2000)

    def show_info_win(self):
        print(1)
        OpenWin.info(self, self.src)

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

        elif ev.key() in KEY_RATING:
            rating = KEY_RATING.get(ev.key())
            self.wid.set_new_rating(rating=rating)
            self.set_title()

        elif ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if ev.key() == Qt.Key.Key_I:
                self.show_info_win()

        return super().keyPressEvent(ev)

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        vertical_center = a0.size().height() // 2 - self.next_btn.height() // 2
        right_window_side = a0.size().width() - self.next_btn.width()
        self.prev_btn.move(30, vertical_center)
        self.next_btn.move(right_window_side - 30, vertical_center)

        horizontal_center = a0.size().width() // 2 - self.zoom_btns.width() // 2
        bottom_window_side = a0.size().height() - self.zoom_btns.height()
        self.zoom_btns.move(horizontal_center, bottom_window_side - 30)

        x = (a0.size().width() - self.text_label.width()) // 2
        y = (a0.size().height() - self.text_label.height()) // 2
        self.text_label.move(x, y)

        Dynamic.ww_im = self.width()
        Dynamic.hh_im = self.height()

    def leaveEvent(self, a0: QEvent | None) -> None:
        self.hide_btns()

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        LoadImage.cache.clear()
        ...

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        menu = UMenu(self)

        open_menu = OpenInApp(menu, self.src)
        menu.addMenu(open_menu)

        menu.addSeparator()

        info = Info(menu, self.src)
        menu.addAction(info)

        show_in_finder_action = RevealInFinder(menu, self.src)
        menu.addAction(show_in_finder_action)

        copy_path = CopyPath(menu, self.src)
        menu.addAction(copy_path)

        menu.addSeparator()

        rating_menu = RatingMenu(menu, self.src, self.wid.rating)
        rating_menu._clicked.connect(self.wid.set_new_rating)
        menu.addMenu(rating_menu)

        menu.exec_(self.mapToGlobal(a0.pos()))
