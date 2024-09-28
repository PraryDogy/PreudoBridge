import os

import sqlalchemy
from PyQt5.QtCore import (QEvent, QObject, QPoint, QSize, Qt, QThread, QTimer,
                          pyqtSignal)
from PyQt5.QtGui import (QImage, QKeyEvent, QMouseEvent, QPainter, QPaintEvent,
                         QPixmap, QResizeEvent)
from PyQt5.QtWidgets import (QFrame, QHBoxLayout, QLabel, QSpacerItem,
                             QVBoxLayout, QWidget)

from cfg import Config
from database import Cache, Dbase
from svg_btn import SvgShadowed
from image_utils import ImageUtils

class Shared:
    loaded_images: dict = {}
    threads: list = []


class LoadImageThread(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, img_src: str):
        super().__init__(parent=None)
        self.img_src = img_src

    def run(self):
        if self.img_src not in Shared.loaded_images:
            src_lower: str = self.img_src.lower()
            img = None

            if os.path.isdir(self.img_src):
                pixmap = QPixmap("images/folder_210.png")

            elif src_lower.endswith((".psd", ".psb")):
                img = ImageUtils.read_psd(self.img_src)

            elif src_lower.endswith((".tiff", ".tif")):
                img = ImageUtils.read_tiff(self.img_src)

            elif src_lower.endswith((".jpg", ".jpeg")):
                img = ImageUtils.read_jpg(self.img_src)

            elif src_lower.endswith((".png")):
                img = ImageUtils.read_png(self.img_src)

            else:
                pixmap = QPixmap("images/folder_210.png")

            if img is not None:
                height, width, channel = img.shape
                bytes_per_line = channel * width
                qimage = QImage(img.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qimage)

        if len(Shared.loaded_images) > 50:
            Shared.loaded_images.pop(next(iter(Shared.loaded_images)))

        self.finished.emit(
            {"image": pixmap,
             "width": pixmap.width(),
             "src": self.img_src
             }
             )

class ImageWidget(QLabel):
    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

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
        return super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev: QMouseEvent | None) -> None:
        if ev.buttons() == Qt.MouseButton.LeftButton and self.scale_factor > 1.0:
            delta = ev.pos() - self.last_mouse_pos
            self.offset += delta
            self.last_mouse_pos = ev.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.update()
        return super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev: QMouseEvent | None) -> None:
        if self.scale_factor > 1.0:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        return super().mouseReleaseEvent(ev)

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
        return super().paintEvent(a0)

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        self.w, self.h = self.width(), self.height()
        self.update()
        return super().resizeEvent(a0)
    

class ZoomBtns(QFrame):
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(h_layout)

        h_layout.addSpacerItem(QSpacerItem(5, 0))

        self.zoom_out = SvgShadowed(os.path.join("images", "zoom_out.svg"), 45)
        h_layout.addWidget(self.zoom_out)
        h_layout.addSpacerItem(QSpacerItem(10, 0))

        self.zoom_in = SvgShadowed(os.path.join("images", "zoom_in.svg"), 45)
        h_layout.addWidget(self.zoom_in)
        h_layout.addSpacerItem(QSpacerItem(10, 0))

        self.zoom_fit = SvgShadowed(os.path.join("images", "zoom_fit.svg"), 45)
        h_layout.addWidget(self.zoom_fit)
        h_layout.addSpacerItem(QSpacerItem(10, 0))

        self.zoom_close = SvgShadowed(os.path.join("images", "zoom_close.svg"), 45)
        h_layout.addWidget(self.zoom_close)

        h_layout.addSpacerItem(QSpacerItem(5, 0))

        self.adjustSize()


class SwitchImageBtn(QFrame):
    def __init__(self, icon_name: str, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setFixedSize(54, 54)

        v_layout = QVBoxLayout()
        v_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(v_layout)

        btn = SvgShadowed(os.path.join("images", icon_name), 50)
        v_layout.addWidget(btn)


class PrevImageBtn(SwitchImageBtn):
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__("prev.svg", parent)


class NextImageBtn(SwitchImageBtn):
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__("next.svg", parent)


class WinImageView(QWidget):
    def __init__(self, parent: QWidget, img_src: str):
        super().__init__()

        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumSize(QSize(300, 200))

        x, y = parent.x(), parent.y()
        w, h = Config.json_data["ww"], Config.json_data["hh"]
        self.setGeometry(x, y, w, h)

        self.v_layout = QVBoxLayout()
        self.v_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.v_layout)

        self.installEventFilter(self)

        self.img_src = img_src

        self.mouse_move_timer = QTimer(self)
        self.mouse_move_timer.setSingleShot(True)
        self.mouse_move_timer.timeout.connect(self.hide_all_buttons)

        self.image_label = ImageWidget()
        self.v_layout.addWidget(self.image_label)

        self.prev_image_btn = PrevImageBtn(self)
        self.prev_image_btn.mouseReleaseEvent = lambda e: self.button_switch_cmd("-")

        self.next_image_btn = NextImageBtn(self)
        self.next_image_btn.mouseReleaseEvent = lambda e: self.button_switch_cmd("+")

        self.zoom_btns = ZoomBtns(parent=self)
        self.zoom_btns.zoom_in.mouseReleaseEvent = lambda e: self.image_label.zoom_in()
        self.zoom_btns.zoom_out.mouseReleaseEvent = lambda e: self.image_label.zoom_out()
        self.zoom_btns.zoom_fit.mouseReleaseEvent = lambda e: self.image_label.zoom_reset()
        self.zoom_btns.zoom_close.mouseReleaseEvent = self.close

        self.hide_all_buttons()
        self.load_thumbnail()

# SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM
                
    def load_thumbnail(self):
        if self.img_src not in Shared.loaded_images:
            self.setWindowTitle("Загрузка")

            q = (sqlalchemy.select(Cache.img)
                .filter(Cache.src == self.img_src))
            session = Dbase.get_session()

            try:
                thumbnail = session.execute(q).first()[0]
                session.close()
            except Exception as e:
                print(e)
                return

            pixmap = QPixmap()
            pixmap.loadFromData(thumbnail)
            self.image_label.set_image(pixmap)

        self.load_image_thread()

    def load_image_thread(self):
        img_thread = LoadImageThread(self.img_src)
        Shared.threads.append(img_thread)
        img_thread.finished.connect(self.load_image_finished)
        img_thread.start()

    def load_image_finished(self, data: dict):
        if data["width"] == 0 or data["src"] != self.img_src:
            return
                        
        self.image_label.set_image(data["image"])
        self.set_image_title()

# GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI

    def hide_all_buttons(self):
        for i in (self.prev_image_btn, self.next_image_btn, self.zoom_btns):
            if i.underMouse():
                return
        self.zoom_btns.hide()
        self.prev_image_btn.hide()
        self.next_image_btn.hide()

    def switch_image(self, offset):
        try:
            keys = list(Config.img_viewer_images.keys())
            current_index = keys.index(self.img_src)
        except Exception as e:
            keys = list(Config.img_viewer_images.keys())
            current_index = 0

        total_images = len(Config.img_viewer_images)
        new_index = (current_index + offset) % total_images
        self.img_src = keys[new_index]
        self.load_thumbnail()

    def cut_text(self, text: str) -> str:
        limit = 40
        if len(text) > limit:
            return text[:limit] + "..."
        return text

    def set_image_title(self):
        name = self.cut_text(os.path.basename(self.img_src))
        self.setWindowTitle(name)

    def button_switch_cmd(self, flag: str) -> None:
        if flag == "+":
            self.switch_image(1)
        else:
            self.switch_image(-1)
        self.setFocus()
        self.image_label.setCursor(Qt.CursorShape.ArrowCursor)

# EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS 

    def keyPressEvent(self, ev: QKeyEvent | None) -> None:
        if ev.key() == Qt.Key.Key_Left:
            self.switch_image(-1)

        elif ev.key() == Qt.Key.Key_Right:
            self.switch_image(1)

        elif ev.key() == Qt.Key.Key_Escape:
            self.close()

        elif ev.key() == Qt.Key.Key_Equal:
            self.image_label.zoom_in()

        elif ev.key() == Qt.Key.Key_Minus:
            self.image_label.zoom_out()

        elif ev.key() == Qt.Key.Key_0:
            self.image_label.zoom_reset()

        return super().keyPressEvent(ev)

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        vertical_center = a0.size().height() // 2 - self.next_image_btn.height() // 2
        right_window_side = a0.size().width() - self.next_image_btn.width()
        self.prev_image_btn.move(10, vertical_center)
        self.next_image_btn.move(right_window_side - 10, vertical_center)

        horizontal_center = a0.size().width() // 2 - self.zoom_btns.width() // 2
        bottom_window_side = a0.size().height() - self.zoom_btns.height()
        self.zoom_btns.move(horizontal_center, bottom_window_side - 50)

        return super().resizeEvent(a0)

    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if a1.type() == 129:
            self.mouse_move_timer.stop()
            self.prev_image_btn.show()
            self.next_image_btn.show()
            self.zoom_btns.show()
            self.mouse_move_timer.start(2000)
        return super().eventFilter(a0, a1)

    def leaveEvent(self, a0: QEvent | None) -> None:
        self.hide_all_buttons()
        return super().leaveEvent(a0)
