import gc
import os

import sqlalchemy
from PyQt5.QtCore import QEvent, QObject, QPoint, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import (QColor, QContextMenuEvent, QKeyEvent, QMouseEvent,
                         QPainter, QPaintEvent, QPixmap, QPixmapCache,
                         QResizeEvent)
from PyQt5.QtWidgets import (QFrame, QHBoxLayout, QLabel, QSpacerItem,
                             QVBoxLayout, QWidget)

from cfg import Static
from database import CACHE, Dbase
from utils import Utils

from ._base_items import (UMenu, URunnable, USvgSqareWidget, UThreadPool,
                          WinBase)
from .actions import ItemActions
from .grid import KEY_RATING, RATINGS, Thumb
from .info_win import InfoWin


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
        self.src = Utils.normalize_slash(src)
        self.name = os.path.basename(self.src)

    def task(self):
        db = os.path.join(os.path.dirname(self.src), Static.DB_FILENAME)
        dbase = Dbase()
        engine = dbase.create_engine(path=db)

        if engine is None:
            image_data = ImageData(self.src, None)
            self.signals_.finished_.emit(image_data)
            return

        conn = Dbase.open_connection(engine)

        q = sqlalchemy.select(CACHE.c.img)
        q = q.where(CACHE.c.name == Utils.get_hash_filename(self.name))
        res = conn.execute(q).scalar() or None

        Dbase.close_connection(conn)

        if res is not None:
            img_array = Utils.bytes_to_array(res)
            img_array = Utils.desaturate_image(img_array, 0.2)
        else:
            img_array = None

        if img_array is None:
            pixmap = None

        else:
            pixmap = Utils.pixmap_from_array(img_array)

        image_data = ImageData(self.src, pixmap)

        try:
            self.signals_.finished_.emit(image_data)
        except RuntimeError as e:
            Utils.print_error(e)


class LoadImage(URunnable):
    def __init__(self, src: str, cached_images: dict[str, QPixmap]):
        super().__init__()
        self.signals_ = WorkerSignals()
        self.src: str = src
        self.cached_images = cached_images

    def task(self):
        if self.src not in self.cached_images:

            img_array = Utils.read_image(self.src)
            img_array = Utils.desaturate_image(img_array, 0.2)

            if img_array is None:
                pixmap = None

            else:
                pixmap = Utils.pixmap_from_array(img_array)
                self.cached_images[self.src] = pixmap

        else:
            pixmap = self.cached_images.get(self.src)
        if len(self.cached_images) > 50:
            first_img = list(self.cached_images.keys())[0]
            self.cached_images.pop(first_img)

        image_data = ImageData(self.src, pixmap)
        self.signals_.finished_.emit(image_data)

        # === очищаем ссылки
        del pixmap
        self.signals_ = None
        gc.collect()
        QPixmapCache.clear()


class ImgWid(QLabel):
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
        return super().resizeEvent(a0)


class ZoomBtns(QFrame):
    cmd_close = pyqtSignal()
    cmd_in = pyqtSignal()
    cmd_out = pyqtSignal()
    cmd_fit = pyqtSignal()

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"""
            background-color: rgba(128, 128, 128, 0.5);
            border-radius: 15px;
            """
            )

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(h_layout)

        h_layout.addSpacerItem(QSpacerItem(5, 0))

        self.zoom_out = USvgSqareWidget(Static.ZOOM_OUT_SVG, 45)
        self.zoom_out.mouseReleaseEvent = lambda e: self.cmd_out.emit()
        h_layout.addWidget(self.zoom_out)
        h_layout.addSpacerItem(QSpacerItem(10, 0))

        self.zoom_in = USvgSqareWidget(Static.ZOOM_IN_SVG, 45)
        self.zoom_in.mouseReleaseEvent = lambda e: self.cmd_in.emit()
        h_layout.addWidget(self.zoom_in)
        h_layout.addSpacerItem(QSpacerItem(10, 0))

        self.zoom_fit = USvgSqareWidget(Static.ZOOM_FIT_SVG, 45)
        self.zoom_fit.mouseReleaseEvent = lambda e: self.cmd_fit.emit()
        h_layout.addWidget(self.zoom_fit)
        h_layout.addSpacerItem(QSpacerItem(10, 0))

        self.zoom_close = USvgSqareWidget(Static.CLOSE_SVG, 45)
        self.zoom_close.mouseReleaseEvent = lambda e: self.cmd_close.emit()
        h_layout.addWidget(self.zoom_close)

        h_layout.addSpacerItem(QSpacerItem(5, 0))

        self.adjustSize()


class SwitchImgBtn(QFrame):
    pressed = pyqtSignal()

    def __init__(self, src: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(54, 54)

        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(v_layout)

        btn = USvgSqareWidget(src, 50)
        v_layout.addWidget(btn)

    def mouseReleaseEvent(self, a0):
        self.pressed.emit()
        return super().mouseReleaseEvent(a0)


class PrevImgBtn(SwitchImgBtn):
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(Static.PREV_SVG, parent)


class NextImgBtn(SwitchImgBtn):
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(Static.NEXT_SVG, parent)


class ImgViewWin(WinBase):
    task_count_limit = 10
    move_to_wid = pyqtSignal(object)
    move_to_url = pyqtSignal(str)
    new_rating = pyqtSignal(int)
    width_, height_ = 700, 500
    min_width_, min_height_ = 400, 300
    object_name = "win_img_view"
    loading_text = "Загрузка"
    error_text = "Ошибка чтения изображения."

    def __init__(self, current_path: str, url_to_wid: dict[str, Thumb], is_selection: bool):
        super().__init__()
        self.setMinimumSize(QSize(ImgViewWin.min_width_, ImgViewWin.min_height_))
        self.resize(ImgViewWin.width_, ImgViewWin.height_)
        self.setObjectName(ImgViewWin.object_name)
        self.setStyleSheet(
            f"""#{ImgViewWin.object_name} {{background: black}}"""
        )

        self.is_selection = is_selection
        self.url_to_wid: dict[str, Thumb] = url_to_wid
        self.urls: list = [i for i in self.url_to_wid]
        self.task_count: int = 0
        self.current_path: str = current_path
        self.current_thumb: Thumb = self.url_to_wid.get(current_path)
        self.current_thumb.text_changed.connect(self.set_title)
        self.cached_images: dict[str, QPixmap] = {}

        self.mouse_move_timer = QTimer(self)
        self.mouse_move_timer.setSingleShot(True)
        self.mouse_move_timer.timeout.connect(self.hide_btns)

        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(v_layout)

        self.img_wid = ImgWid()
        self.img_wid.mouse_moved.connect(self.show_btns)
        v_layout.addWidget(self.img_wid)

        self.prev_btn = PrevImgBtn(self)
        self.prev_btn.pressed.connect(lambda: self.switch_img_btn("-"))

        self.next_btn = NextImgBtn(self)
        self.next_btn.pressed.connect(lambda: self.switch_img_btn("+"))

        self.zoom_btns = ZoomBtns(parent=self)
        self.zoom_btns.cmd_in.connect(self.img_wid.zoom_in)
        self.zoom_btns.cmd_out.connect(self.img_wid.zoom_out)
        self.zoom_btns.cmd_fit.connect(self.img_wid.zoom_reset)
        self.zoom_btns.cmd_close.connect(self.deleteLater)

        self.loading_label = QLabel(parent=self.img_wid)
        self.loading_label.hide()

        self.hide_btns()
        self.resize(ImgViewWin.width_ + 1, ImgViewWin.height_ + 1)

        self.loading_label.hide()
        self.set_title()

        if self.current_path.endswith(Static.ext_all):
            QTimer.singleShot(100 , self.load_thumbnail)

# SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM

    def set_title(self):
        text_ = os.path.basename(self.current_path)
        if self.current_thumb.rating > 0:
            text_ = f"{RATINGS[self.current_thumb.rating]} | {text_}"
        self.setWindowTitle(text_)

    def load_thumbnail(self):
        if self.current_path not in self.cached_images:
            self.task_ = LoadThumbnail(self.current_path)
            cmd_ = lambda image_data: self.load_thumbnail_finished(image_data)
            self.task_.signals_.finished_.connect(cmd_)
            UThreadPool.start(self.task_)

        else:
            self.show_text_label(ImgViewWin.loading_text)
            self.load_image()

    def show_text_label(self, text: str):
        pixmap = QPixmap(1, 1)
        pixmap.fill(QColor(0, 0, 0))
        self.img_wid.set_image(pixmap)
        self.loading_label.setText(text)
        self.loading_label.show()

    def load_thumbnail_finished(self, image_data: ImageData):
        if image_data.pixmap is None:
            self.show_text_label(ImgViewWin.loading_text)

        elif image_data.src == self.current_path:
            self.img_wid.set_image(image_data.pixmap)

        self.load_image()

    def load_image(self):
        self.task_count += 1
        self.task_ = LoadImage(self.current_path, self.cached_images)
        cmd_ = lambda image_data: self.load_image_finished(image_data)
        self.task_.signals_.finished_.connect(cmd_)
        UThreadPool.start(self.task_)

    def load_image_finished(self, image_data: ImageData):
        self.task_count -= 1
        self.loading_label.hide()
        if image_data.pixmap is None:
            self.show_text_label(ImgViewWin.error_text)
        elif image_data.src == self.current_path:
            self.img_wid.set_image(image_data.pixmap)


# GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI

    def hide_btns(self):
        for i in (self.prev_btn, self.next_btn, self.zoom_btns):
            if i.underMouse():
                return
        self.zoom_btns.hide()
        self.prev_btn.hide()
        self.next_btn.hide()

    def switch_img(self, offset: int):
        if self.task_count == ImgViewWin.task_count_limit:
            return

        try:
            current_index: int = self.urls.index(self.current_path)
        except ValueError:
            current_index: int = 0

        total_images: int = len(self.urls)
        new_index: int = (current_index + offset) % total_images

        self.current_path: str = self.urls[new_index]

        self.current_thumb.text_changed.disconnect()
        self.current_thumb: Thumb = self.url_to_wid.get(self.current_path)
        self.current_thumb.text_changed.connect(self.set_title)

        if not self.is_selection:
            self.move_to_wid.emit(self.current_thumb)
            self.move_to_url.emit(self.current_path)

        self.loading_label.hide()
        self.set_title()
        self.load_thumbnail()

    def switch_img_btn(self, flag: str) -> None:
        if flag == "+":
            self.switch_img(1)
        else:
            self.switch_img(-1)
        self.img_wid.setCursor(Qt.CursorShape.ArrowCursor)

    def show_btns(self):
        self.mouse_move_timer.stop()
        self.prev_btn.show()
        self.next_btn.show()
        self.zoom_btns.show()
        self.mouse_move_timer.start(2000)

    def win_info_cmd(self, src: str):
        self.win_info = InfoWin(src)
        self.win_info.center(self)
        self.win_info.show()

# EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS 

    def keyPressEvent(self, ev: QKeyEvent | None) -> None:
        if ev.key() == Qt.Key.Key_Left:
            self.switch_img(-1)

        elif ev.key() == Qt.Key.Key_Right:
            self.switch_img(1)

        elif ev.key() == Qt.Key.Key_Escape:
            self.deleteLater()

        elif ev.key() == Qt.Key.Key_Equal:
            self.img_wid.zoom_in()

        elif ev.key() == Qt.Key.Key_Minus:
            self.img_wid.zoom_out()

        elif ev.key() == Qt.Key.Key_0:
            self.img_wid.zoom_reset()

        elif ev.key() == Qt.Key.Key_Space:
            self.deleteLater()

        elif ev.key() in KEY_RATING:
            rating = KEY_RATING.get(ev.key())
            self.new_rating.emit(rating)
            self.set_title()

        elif ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if ev.key() == Qt.Key.Key_I:
                self.win_info_cmd(self.current_path)

        return super().keyPressEvent(ev)

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        # у нас отложенная инициация дочерних виджетов, поэтому при инициации
        # окна вылезет ошибка аттрибута
        try:
            vertical_center = a0.size().height() // 2 - self.next_btn.height() // 2
        except AttributeError:
            return

        right_window_side = a0.size().width() - self.next_btn.width()
        self.prev_btn.move(30, vertical_center)
        self.next_btn.move(right_window_side - 30, vertical_center)

        horizontal_center = a0.size().width() // 2 - self.zoom_btns.width() // 2
        bottom_window_side = a0.size().height() - self.zoom_btns.height()
        self.zoom_btns.move(horizontal_center, bottom_window_side - 30)

        x = (a0.size().width() - self.loading_label.width()) // 2
        y = (a0.size().height() - self.loading_label.height()) // 2
        self.loading_label.move(x, y)

        ImgViewWin.width_ = self.width()
        ImgViewWin.height_ = self.height()

        return super().resizeEvent(a0)

    def leaveEvent(self, a0: QEvent | None) -> None:
        self.hide_btns()

    def deleteLater(self):
        self.cached_images.clear()
        QPixmapCache.clear()
        gc.collect()
        return super().deleteLater()

    def closeEvent(self, a0):
        self.cached_images.clear()
        QPixmapCache.clear()
        gc.collect()
        return super().closeEvent(a0)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        urls = [self.current_path]
        names = [os.path.basename(i) for i in urls]
        total = len(urls)

        menu = UMenu(parent=self)

        open_menu = ItemActions.OpenInApp(menu, self.current_path)
        menu.addMenu(open_menu)

        menu.addSeparator()

        info = ItemActions.Info(menu)
        info.triggered.connect(lambda: self.win_info_cmd(self.current_path))
        menu.addAction(info)

        show_in_finder_action = ItemActions.RevealInFinder(menu, urls, total)
        menu.addAction(show_in_finder_action)

        copy_path = ItemActions.CopyPath(menu, urls, total)
        menu.addAction(copy_path)

        copy_name = ItemActions.CopyName(menu, names, total)
        menu.addAction(copy_name)

        menu.addSeparator()

        rating_menu = ItemActions.RatingMenu(menu, urls, total, self.current_thumb.rating)
        rating_menu.new_rating.connect(lambda value: self.new_rating.emit(value))
        menu.addMenu(rating_menu)

        menu.show_()