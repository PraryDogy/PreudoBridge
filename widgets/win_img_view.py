import os
import subprocess

import sqlalchemy
from PyQt5.QtCore import QEvent, QPoint, QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import (QCloseEvent, QContextMenuEvent, QKeyEvent,
                         QMouseEvent, QPainter, QPaintEvent, QPixmap,
                         QResizeEvent)
from PyQt5.QtWidgets import (QAction, QFrame, QHBoxLayout, QLabel, QMenu,
                             QSpacerItem, QVBoxLayout, QWidget)
import sqlalchemy.exc

from cfg import Config
from database import Cache, Dbase
from utils import Utils

from .svg_widgets import SvgShadowed


class Shared:
    loaded_images: dict[str: QPixmap] = {}
    threads: list[QThread] = []


class LoadImageThread(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, img_src: str):
        super().__init__(parent=None)
        self.img_src: str = img_src

    def run(self):
        if self.img_src not in Shared.loaded_images:
            img = Utils.read_image(self.img_src)
            if img is not None:
                pixmap = Utils.pixmap_from_array(img)
                Shared.loaded_images[self.img_src] = pixmap
            else:
                pixmap = QPixmap("images/file_210.png")
        else:
            pixmap = Shared.loaded_images.get(self.img_src)

        if len(Shared.loaded_images) > 50:
            first_img = list(Shared.loaded_images.keys())[0]
            Shared.loaded_images.pop(first_img)

        self.finished.emit(
            {"image": pixmap,
             "width": pixmap.width(),
             "src": self.img_src
             }
             )

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


class WinImgView(QWidget):
    closed = pyqtSignal(str)

    def __init__(self, img_src: str, paths: list):
        super().__init__()
        self.img_src: str = img_src
        self.paths: list = paths

        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumSize(QSize(400, 300))
        self.resize(Config.json_data.get("ww_im"), Config.json_data.get("hh_im"))
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

        self.image_label = ImageWidget()
        self.image_label.mouse_moved.connect(self.mouse_moved_cmd)
        self.v_layout.addWidget(self.image_label)

        self.prev_image_btn = PrevImageBtn(self)
        self.prev_image_btn.pressed.connect(lambda: self.button_switch_cmd("-"))

        self.next_image_btn = NextImageBtn(self)
        self.next_image_btn.pressed.connect(lambda: self.button_switch_cmd("+"))

        self.zoom_btns = ZoomBtns(parent=self)
        self.zoom_btns.zoomed_in.connect(self.image_label.zoom_in)
        self.zoom_btns.zoomed_out.connect(self.image_label.zoom_out)
        self.zoom_btns.zoomed_fit.connect(self.image_label.zoom_reset)
        self.zoom_btns.press_close.connect(self.close)

        self.context_menu = QMenu(self)

        open_action = QAction("Открыть по умолчанию", self)
        open_action.triggered.connect(self.open_default)
        self.context_menu.addAction(open_action)

        show_in_finder_action = QAction("Показать в Finder", self)
        show_in_finder_action.triggered.connect(self.show_in_finder)
        self.context_menu.addAction(show_in_finder_action)

        copy_path = QAction("Скопировать путь до файла", self)
        copy_path.triggered.connect(lambda: Utils.copy_path(self.img_src))
        self.context_menu.addAction(copy_path)

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
                pixmap = QPixmap()
                pixmap.loadFromData(thumbnail)
                self.image_label.set_image(pixmap)
            except (sqlalchemy.exc.OperationalError, Exception) as e:
                print("IMG VIEW: there is no thumbnail in db")
                # тут в pixmap надо загрузить изображение файла

        self.load_image_thread()

    def load_image_thread(self):
        self.setWindowTitle("Загрузка")
        img_thread = LoadImageThread(self.img_src)
        Shared.threads.append(img_thread)
        img_thread.finished.connect(
            lambda data: self.load_image_finished(img_thread, data)
            )
        img_thread.start()

    def load_image_finished(self, thread: LoadImageThread, data: dict):
        if data.get("width") == 0 or data.get("src") != self.img_src:
            return
                        
        self.image_label.set_image(data.get("image"))
        self.setWindowTitle(os.path.basename(self.img_src))
        Shared.threads.remove(thread)

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
            current_index = self.paths.index(self.img_src)
        except Exception as e:
            current_index = 0

        total_images = len(self.paths)
        new_index = (current_index + offset) % total_images

        self.img_src = self.paths[new_index]
        self.load_thumbnail()

    def button_switch_cmd(self, flag: str) -> None:
        if flag == "+":
            self.switch_image(1)
        else:
            self.switch_image(-1)
        self.image_label.setCursor(Qt.CursorShape.ArrowCursor)

    def mouse_moved_cmd(self):
        self.mouse_move_timer.stop()
        self.prev_image_btn.show()
        self.next_image_btn.show()
        self.zoom_btns.show()
        self.mouse_move_timer.start(2000)

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

        elif ev.key() == Qt.Key.Key_Space:
            self.close()

        return super().keyPressEvent(ev)

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        vertical_center = a0.size().height() // 2 - self.next_image_btn.height() // 2
        right_window_side = a0.size().width() - self.next_image_btn.width()
        self.prev_image_btn.move(30, vertical_center)
        self.next_image_btn.move(right_window_side - 30, vertical_center)

        horizontal_center = a0.size().width() // 2 - self.zoom_btns.width() // 2
        bottom_window_side = a0.size().height() - self.zoom_btns.height()
        self.zoom_btns.move(horizontal_center, bottom_window_side - 30)

        Config.json_data["ww_im"] = self.width()
        Config.json_data["hh_im"] = self.height()

        # return super().resizeEvent(a0)

    def leaveEvent(self, a0: QEvent | None) -> None:
        self.hide_all_buttons()
        # return super().leaveEvent(a0)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        Shared.loaded_images.clear()
        self.closed.emit(self.img_src)
        # return super().closeEvent(a0)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        self.context_menu.exec_(self.mapToGlobal(a0.pos()))
    
    def open_default(self):
        subprocess.call(["open", self.img_src])

    def show_in_finder(self):
        subprocess.call(["open", "-R", self.img_src])