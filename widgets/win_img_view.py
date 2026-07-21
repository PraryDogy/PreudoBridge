import gc
import os
from multiprocessing import shared_memory

import numpy as np
from PyQt6.QtCore import QEvent, QPointF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (QContextMenuEvent, QCursor, QImage, QKeyEvent,
                         QMouseEvent, QPixmap, QResizeEvent, QTransform)
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import (QApplication, QGraphicsOpacityEffect,
                             QGraphicsPixmapItem, QGraphicsScene,
                             QGraphicsView, QLabel, QVBoxLayout)

from system.items import DataItem, ImgViewItem, ReadImgItem
from system.multiprocess import ProcessWorker, ReadImg
from system.tasks import ImgArrayQImage, UThreadPool

from ._base_widgets import BaseSignals, UMainWindow, UMenu
from .actions import Actions, Menus


class ImgWid(QGraphicsView):
    mouse_moved = pyqtSignal()

    def __init__(self, pixmap: QPixmap = None):
        super().__init__()

        self.setMouseTracking(True)
        self.setStyleSheet("background: black")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.scene_ = QGraphicsScene()
        self.setScene(self.scene_)

        self.pixmap_item: QGraphicsPixmapItem = None
        self._last_mouse_pos: QPointF = None
        self.is_zoomed = False

        if pixmap:
            self.pixmap_item = QGraphicsPixmapItem(pixmap)
            self.scene_.addItem(self.pixmap_item)
            self.resetTransform()
            self.horizontalScrollBar().setValue(0)
            self.verticalScrollBar().setValue(0)

    def zoom_in(self):
        self.scale(1.1, 1.1)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.is_zoomed = True

    def zoom_out(self):
        self.scale(0.9, 0.9)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.is_zoomed = True

    def zoom_fit(self):
        if self.pixmap_item:
            self.resetTransform()
            self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            self.is_zoomed = False
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_transparent(self, value: float):
        effect = QGraphicsOpacityEffect(self)
        effect.setOpacity(value)
        self.pixmap_item.setGraphicsEffect(effect)

    # ---------------------- Drag через мышь ----------------------
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._last_mouse_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        self.mouse_moved.emit()
        if self._last_mouse_pos and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.pos() - self._last_mouse_pos
            self._last_mouse_pos = event.pos()

            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.is_zoomed:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        self._last_mouse_pos = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        # Если это стрелки, не обрабатываем их здесь
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            event.ignore()  # передаём событие родителю
            return
        # для остальных клавиш можно оставить стандартную обработку
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.pixmap_item:
            self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)


class CustomSvg(QSvgWidget):
    clicked = pyqtSignal()
    svg_size = 50

    def __init__(self):
        super().__init__()
        self.setStyleSheet(
            """
                background: transparent;
            """
        )

    def load(self, file_path: str):
        super().load(file_path)
        renderer = self.renderer()
        if renderer and renderer.isValid():
            orig_size = renderer.defaultSize()
            aspect_ratio = orig_size.width() / orig_size.height()
            calculated_width = int(self.svg_size * aspect_ratio)
            self.setFixedSize(calculated_width, self.svg_size)

    def mouseReleaseEvent(self, a0: QMouseEvent):
        if a0.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        return super().mouseReleaseEvent(a0)


class ZoomWidget(CustomSvg):
    zoom_close = pyqtSignal()
    zoom_in = pyqtSignal()
    zoom_out = pyqtSignal()
    zoom_fit = pyqtSignal()
    svg_path = "./images/zoom.svg"

    def __init__(self):
        super().__init__()
        self.load(self.svg_path)
        self.zone_width = self.width() / 4
        self.start_pos = None
        self.is_move = False

    def mousePressEvent(self, e: QMouseEvent):
        self.start_pos = e.pos()
        self.is_move = False
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent):
        if not self.start_pos:
            return
        dx = e.pos().x() - self.start_pos.x()
        if abs(dx) > 30:  # горизонтальное движение
            self.is_move = True
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            if dx > 0:
                self.zoom_in.emit()
            else:
                self.zoom_out.emit()
            self.start_pos = e.pos()
        super().mouseMoveEvent(e)


    def mouseReleaseEvent(self, a0: QMouseEvent):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        if self.is_move:
            self.is_move = False
            return  # не считаем клик, если двигали мышь

        zone_index = int(a0.pos().x() // self.zone_width)
        if zone_index == 0:
            self.zoom_out.emit()
        elif zone_index == 1:
            self.zoom_in.emit()
        elif zone_index == 2:
            self.zoom_fit.emit()
        else:
            self.zoom_close.emit()
        return super().mouseReleaseEvent(a0)


class PrevButton(CustomSvg):
    svg_path = "./images/prev.svg"

    def __init__(self) -> None:
        super().__init__()
        self.load(self.svg_path)


class NextButton(CustomSvg):
    svg_path = "./images/next.svg"

    def __init__(self) -> None:
        super().__init__()
        self.load(self.svg_path)


class WinImgView(UMainWindow):
    cached_images: dict[str, QImage] = {}
    object_name = "win_img_view"
    loading_text = "Загрузка"
    error_text = "Ошибка чтения изображения."
    min_w, min_h = 400, 300
    ww, hh = 0, 0
    xx, yy = 0, 0

    move_to_wid = pyqtSignal(DataItem)
    closed = pyqtSignal()

    def __init__(self, item: ImgViewItem):
        super().__init__()
        self.setMinimumSize(QSize(self.min_w, self.min_h))
        self.setObjectName(self.object_name)
        self.setStyleSheet(
            f"""#{self.object_name} {{background: black}}"""
        )
        
        self.base_signals = BaseSignals()
        self.read_img_task = None
        self.is_selection = item.is_selection
        self.url_to_data_item: dict[str, DataItem] = item.url_to_data_item
        self.urls: list = list(self.url_to_data_item.keys())
        self.current_url = item.current_url
        self.current_data_item = self.url_to_data_item[self.current_url]

        self.mouse_move_timer = QTimer(self)
        self.mouse_move_timer.setSingleShot(True)
        self.mouse_move_timer.timeout.connect(self.hide_btns)

        self.v_layout = QVBoxLayout(self.centralWidget())
        self.v_layout.setContentsMargins(0, 0, 0, 0)

        self.img_wid = ImgWid(QPixmap())
        self.img_wid.mouse_moved.connect(self.show_btns)
        self.v_layout.addWidget(self.img_wid)

        self.prev_btn = PrevButton()
        self.prev_btn.setParent(self)
        self.prev_btn.clicked.connect(lambda: self.switch_img(-1))

        self.next_btn = NextButton()
        self.next_btn.setParent(self)
        self.next_btn.clicked.connect(lambda: self.switch_img(1))

        self.zoom_btns = ZoomWidget()
        self.zoom_btns.setParent(self)
        self.zoom_btns.zoom_in.connect(lambda: self.zoom_cmd("in"))
        self.zoom_btns.zoom_out.connect(lambda: self.zoom_cmd("out"))
        self.zoom_btns.zoom_fit.connect(lambda: self.zoom_cmd("fit"))
        self.zoom_btns.zoom_close.connect(self.deleteLater)

        self.text_label = QLabel(self)
        self.text_label.setStyleSheet("background: black;")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.first_load()

# SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM

    def first_load(self):
        self.load_thumbnail()

    def zoom_cmd(self, flag: str):
        actions = {
            "in": self.img_wid.zoom_in,
            "out": self.img_wid.zoom_out,
            "fit": self.img_wid.zoom_fit,
        }
        actions[flag]()

    def set_title(self):
        text_ = os.path.basename(self.current_url)
        self.setWindowTitle(text_)

    def load_thumbnail(self):
        self.set_title()
        self.text_label.hide()

        if self.current_url in WinImgView.cached_images:
            pixmap = WinImgView.cached_images[self.current_url]
            self.restart_img_wid(pixmap)
        else:
            self.load_image()
        return
        if self.current_data_item.qimages:
            qimage = self.current_data_item.qimages["src"]
            pixmap = QPixmap.fromImage(qimage)
            self.restart_img_wid(pixmap)
            self.load_image()
        else:
            t = f"{os.path.basename(self.current_url)}\n{self.loading_text}"
            self.show_text_label(t)
            self.load_image()

    def show_text_label(self, text: str):
        self.text_label.setText(text)
        self.text_label.raise_()  # поверх остальных
        self.text_label.show()

    def restart_img_wid(self, pixmap: QPixmap):
        self.text_label.hide()
        self.img_wid.hide()  # скрываем старый
        new_wid = ImgWid(pixmap)
        new_wid.mouse_moved.connect(self.show_btns)
        self.v_layout.addWidget(new_wid)

        self.img_wid.deleteLater()
        self.img_wid = new_wid
        self.img_wid.show()
        self.img_wid.lower()

        btns = (self.prev_btn, self.next_btn, self.zoom_btns)
        for i in btns:
            i.raise_()

    def load_image(self, ms: int = 500):
        def fin(src: str, qimage: QImage, shm: shared_memory.SharedMemory):
            pixmap = QPixmap.fromImage(qimage)
            self.cached_images[src] = pixmap
            self.restart_img_wid(pixmap)

            shm.close()
            shm.unlink()  # освобождаем память

        def poll_task():
            q = self.read_img_task.queue
            if not q.empty():
                item: ReadImgItem = q.get()
                shm = shared_memory.SharedMemory(name=item.shm_name)
                img_array = np.ndarray(item.shape, dtype=np.dtype(item.dtype), buffer=shm.buf)
                if img_array is None:
                    self.show_text_label(self.error_text)
                elif item.src == self.current_url:
                    self.qimage_task = ImgArrayQImage(img_array)
                    self.qimage_task.sigs.finished_.connect(
                            lambda qimage: fin(item.src, qimage, shm)
                    )
                    UThreadPool.start(self.qimage_task)

            if not self.read_img_task.is_alive():
                self.read_img_task.terminate_join()
            else:
                QTimer.singleShot(ms, poll_task)
        
        if self.read_img_task:
            self.read_img_task.terminate_join()

        self.img_wid.set_transparent(0.7)

        self.read_img_task = ProcessWorker(
            target=ReadImg.start,
            args=(self.current_url, True, )
        )
        self.read_img_task.start()
        QTimer.singleShot(ms, poll_task)
        
    def rotate_image(self, value: int):
        pixmap = self.img_wid.pixmap_item.pixmap()
        transform = QTransform().rotate(value)
        rotated = pixmap.transformed(transform)
        self.restart_img_wid(rotated)

# GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI

    def hide_btns(self):
        btns = (self.prev_btn, self.next_btn, self.zoom_btns)
        widget_under_cursor = QApplication.widgetAt(QCursor.pos())
        if isinstance(widget_under_cursor, QSvgWidget):
            return
        for i in btns:
            i.hide()

    def switch_img(self, offset: int):
        if self.current_url in self.urls:
            current_index = self.urls.index(self.current_url)
        else:
            current_index = 0
        total_images = len(self.urls)
        new_index = (current_index + offset) % total_images
        self.current_url = self.urls[new_index]
        try:
            self.current_data_item = self.url_to_data_item[self.current_url]
            if not self.is_selection:
                self.move_to_wid.emit(self.current_data_item)
            self.load_thumbnail()
        except Exception as e:
            print("widgets ImgViewWin error", e)

    def show_btns(self):
        self.mouse_move_timer.stop()
        btn = (self.prev_btn, self.next_btn, self.zoom_btns)
        for i in btn:
            i.show()
        self.mouse_move_timer.start(2000)


# EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS 

    def keyPressEvent(self, ev: QKeyEvent | None) -> None:
        if ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if ev.key() == Qt.Key.Key_I:
                self.base_signals.info.emit([self.current_url, ])

            elif ev.key() == Qt.Key.Key_0:
                self.img_wid.zoom_fit()

            elif ev.key() == Qt.Key.Key_Equal:
                self.img_wid.zoom_in()

            elif ev.key() == Qt.Key.Key_Minus:
                self.img_wid.zoom_out()

            elif ev.key() == Qt.Key.Key_Left:
                self.rotate_image(-90)

            elif ev.key() == Qt.Key.Key_Right:
                self.rotate_image(90)

        else:
            if ev.key() == Qt.Key.Key_Left:
                self.switch_img(-1)

            elif ev.key() == Qt.Key.Key_Right:
                self.switch_img(1)

            elif ev.key() == Qt.Key.Key_Escape:
                if self.isFullScreen():
                    self.showNormal()
                    self.raise_()
                else:
                    self.deleteLater()
            elif ev.key() == Qt.Key.Key_Space:
                self.deleteLater()

        # return super().keyPressEvent(ev)

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

        self.text_label.resize(self.size())
        self.setFocus()

        return super().resizeEvent(a0)

    def leaveEvent(self, a0: QEvent | None) -> None:
        self.hide_btns()

    def on_closed(self):
        WinImgView.ww = self.size().width()
        WinImgView.hh = self.size().height()
        WinImgView.xx = self.x()
        WinImgView.yy = self.y()
        WinImgView.cached_images.clear()
        gc.collect()
        self.closed.emit()

    def deleteLater(self):
        self.on_closed()
        return super().deleteLater()

    def closeEvent(self, a0):
        self.on_closed()
        return super().closeEvent(a0)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        urls = [self.current_url, ]
        self.context_menu = UMenu()
        self.context_actions = Actions(self.context_menu)
        self.context_menus = Menus(self.context_menu)
        self.context_menu.add_menu(
            menu=self.context_menus.open_in_app_menu,
            callback=lambda app_path: self.base_signals.open_in_app.emit((urls, app_path))
        )
        self.context_menu.addSeparator()
        self.context_menu.add_action(
            action=self.context_actions.win_info,
            callback=lambda: self.base_signals.info.emit(urls)
        )
        self.context_menu.add_action(
            action=self.context_actions.reveal,
            callback=lambda: self.base_signals.reveal_urls.emit(urls)
        )
        self.context_menu.addSeparator()
        self.context_menu.add_action(
            action=self.context_actions.copy_path,
            callback=lambda: self.base_signals.copy_urls.emit(urls)
        )
        self.context_menu.add_action(
            action=self.context_actions.copy_name,
            callback=lambda: self.base_signals.copy_names.emit(urls)
        )
        self.context_menu.addSeparator()
        
        self.context_menu.add_action(
            action=self.context_actions.rotate_cw,
            callback=lambda: self.rotate_image(90)
        )

        self.context_menu.add_action(
            action=self.context_actions.rotate_ccw,
            callback=lambda: self.rotate_image(-90)
        )

        self.context_menu.show_under_mouse()
