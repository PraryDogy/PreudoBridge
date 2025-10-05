import os

from PyQt5.QtCore import QEvent, QPoint, QPointF, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import (QColor, QContextMenuEvent, QCursor, QIcon, QImage,
                         QKeyEvent, QMouseEvent, QPainter, QPaintEvent,
                         QPixmap, QResizeEvent, QWheelEvent)
from PyQt5.QtWidgets import (QFrame, QGraphicsPixmapItem, QGraphicsScene,
                             QGraphicsView, QHBoxLayout, QLabel, QScrollBar,
                             QSpacerItem, QVBoxLayout, QWidget)

from cfg import Static
from system.tasks import ReadImg, UThreadPool

from ._base_widgets import UMenu, USvgSqareWidget, WinBase
from .actions import ItemActions
from .grid import KEY_RATING, RATINGS, Thumb
from .info_win import InfoWin

# class ImgWid(QLabel):
#     mouse_moved = pyqtSignal()

#     def __init__(self):
#         super().__init__()
#         self.setAlignment(Qt.AlignmentFlag.AlignCenter)
#         self.setMouseTracking(True)
#         self.setStyleSheet("background: black; color: white;")

#         self.current_pixmap: QPixmap = None
#         self.scale_factor: float = 1.0
#         self.offset = QPoint(0, 0)
#         self.w, self.h = 0, 0

#     def set_image(self, pixmap: QPixmap):
#         self.current_pixmap = pixmap
#         self.scale_factor = 1.0
#         self.offset = QPoint(0, 0)
#         self.setCursor(Qt.CursorShape.ArrowCursor)
#         self.update()

#     def zoom_in(self):
#         self.scale_factor *= 1.1
#         self.setCursor(Qt.CursorShape.OpenHandCursor)
#         self.update()

#     def zoom_out(self):
#         self.scale_factor /= 1.1
#         self.update()

#     def zoom_reset(self):
#         self.scale_factor = 1.0
#         self.offset = QPoint(0, 0)
#         self.setCursor(Qt.CursorShape.ArrowCursor)
#         self.update()

#     def mousePressEvent(self, ev: QMouseEvent | None) -> None:
#         if ev.button() == Qt.MouseButton.LeftButton:
#             self.last_mouse_pos = ev.pos()
#         # return super().mousePressEvent(ev)

#     def mouseMoveEvent(self, ev: QMouseEvent | None) -> None:
#         self.mouse_moved.emit()
#         if ev.buttons() == Qt.MouseButton.LeftButton and self.scale_factor > 1.0:
#             delta = ev.pos() - self.last_mouse_pos
#             self.offset += delta
#             self.last_mouse_pos = ev.pos()
#             self.setCursor(Qt.CursorShape.ClosedHandCursor)
#             self.update()
#         # return super().mouseMoveEvent(ev)

#     def mouseReleaseEvent(self, ev: QMouseEvent | None) -> None:
#         if self.scale_factor > 1.0:
#             self.setCursor(Qt.CursorShape.OpenHandCursor)
#         # return super().mouseReleaseEvent(ev)

#     def paintEvent(self, a0: QPaintEvent | None) -> None:
#         if self.current_pixmap is not None:
#             painter = QPainter(self)
#             scaled_pixmap = self.current_pixmap.scaled(
#                 int(self.w * self.scale_factor),
#                 int(self.h * self.scale_factor),
#                 Qt.AspectRatioMode.KeepAspectRatio,
#                 Qt.TransformationMode.SmoothTransformation
#                 )
#             offset = self.offset + QPoint(
#                 int((self.width() - scaled_pixmap.width()) / 2),
#                 int((self.height() - scaled_pixmap.height()) / 2)
#                 )
#             painter.drawPixmap(offset, scaled_pixmap)
#         return super().paintEvent(a0)

#     def resizeEvent(self, a0: QResizeEvent | None) -> None:
#         self.w, self.h = self.width(), self.height()
#         self.update()
#         return super().resizeEvent(a0)


from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QScrollBar
from PyQt5.QtGui import QPixmap, QMouseEvent, QWheelEvent, QPainter
from PyQt5.QtCore import Qt, QPointF, pyqtSignal, QTimer


class ImgWid(QGraphicsView):
    mouse_moved = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.setMouseTracking(True)
        self.setStyleSheet("background: black; color: white;")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        self.scene_ = QGraphicsScene()
        self.setScene(self.scene_)

        self.pixmap_item: QGraphicsPixmapItem = None
        self.last_mouse_pos: QPointF = None
        self.scale_factor: float = 1.0

    def set_image(self, pixmap: QPixmap):
        """Устанавливает изображение и масштабирует под окно корректно."""
        self.last_mouse_pos = None
        self.scale_factor = 1.0

        self.scene_.clear()
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene_.addItem(self.pixmap_item)

        # Сбрасываем трансформацию и scrollbars
        self.resetTransform()
        self.horizontalScrollBar().setValue(0)
        self.verticalScrollBar().setValue(0)

        # Центрируем с минимальной задержкой, чтобы виджет имел реальные размеры
        QTimer.singleShot(0, lambda: self.fitInView(self.pixmap_item, Qt.KeepAspectRatio))

    def zoom_in(self):
        self.scale(1.1, 1.1)
        self.scale_factor *= 1.1

    def zoom_out(self):
        self.scale(0.9, 0.9)
        self.scale_factor *= 0.9

    def zoom_reset(self):
        """Сбрасывает масштаб и центрирует изображение"""
        if self.pixmap_item:
            self.resetTransform()
            QTimer.singleShot(0, lambda: self.fitInView(self.pixmap_item, Qt.KeepAspectRatio))
            self.scale_factor = 1.0

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.ClosedHandCursor)
            self.last_mouse_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        self.mouse_moved.emit()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(event)


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

        self.zoom_out = USvgSqareWidget(Static.INTERNAL_ICONS.get("zoom_out.svg"), 45)
        self.zoom_out.mouseReleaseEvent = lambda e: self.cmd_out.emit()
        h_layout.addWidget(self.zoom_out)
        h_layout.addSpacerItem(QSpacerItem(10, 0))

        self.zoom_in = USvgSqareWidget(Static.INTERNAL_ICONS.get("zoom_in.svg"), 45)
        self.zoom_in.mouseReleaseEvent = lambda e: self.cmd_in.emit()
        h_layout.addWidget(self.zoom_in)
        h_layout.addSpacerItem(QSpacerItem(10, 0))

        self.zoom_fit = USvgSqareWidget(Static.INTERNAL_ICONS.get("zoom_fit.svg"), 45)
        self.zoom_fit.mouseReleaseEvent = lambda e: self.cmd_fit.emit()
        h_layout.addWidget(self.zoom_fit)
        h_layout.addSpacerItem(QSpacerItem(10, 0))

        self.zoom_close = USvgSqareWidget(Static.INTERNAL_ICONS.get("zoom_close.svg"), 45)
        self.zoom_close.mouseReleaseEvent = lambda e: self.cmd_close.emit()
        h_layout.addWidget(self.zoom_close)

        h_layout.addSpacerItem(QSpacerItem(5, 0))

        self.adjustSize()


class SwitchImgBtn(QFrame):
    pressed = pyqtSignal()

    def __init__(self, src: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(54, 54)

        self.v_layout = QVBoxLayout()
        self.v_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.v_layout)

        btn = USvgSqareWidget(src, 50)
        self.v_layout.addWidget(btn)

    def mouseReleaseEvent(self, a0):
        self.pressed.emit()
        return super().mouseReleaseEvent(a0)


class PrevImgBtn(SwitchImgBtn):
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(Static.INTERNAL_ICONS.get("prev.svg"), parent)


class NextImgBtn(SwitchImgBtn):
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(Static.INTERNAL_ICONS.get("next.svg"), parent)


class ImgViewWin(WinBase):
    task_count_limit = 10
    move_to_wid = pyqtSignal(object)
    move_to_url = pyqtSignal(str)
    new_rating = pyqtSignal(tuple)
    closed = pyqtSignal()
    width_, height_ = 700, 500
    min_width_, min_height_ = 400, 300
    object_name = "win_img_view"
    loading_text = "Загрузка"
    error_text = "Ошибка чтения изображения."

    def __init__(self, start_url: str, url_to_wid: dict[str, Thumb], is_selection: bool):
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
        self.current_path: str = start_url
        self.current_thumb: Thumb = self.url_to_wid.get(start_url)
        self.current_thumb.text_changed.connect(self.set_title)

        self.mouse_move_timer = QTimer(self)
        self.mouse_move_timer.setSingleShot(True)
        self.mouse_move_timer.timeout.connect(self.hide_btns)

        self.v_layout = QVBoxLayout()
        self.v_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.v_layout)

        self.img_wid = ImgWid()
        self.img_wid.mouse_moved.connect(self.show_btns)
        self.v_layout.addWidget(self.img_wid)

        self.prev_btn = PrevImgBtn(self)
        self.prev_btn.pressed.connect(lambda: self.switch_img(-1))

        self.next_btn = NextImgBtn(self)
        self.next_btn.pressed.connect(lambda: self.switch_img(1))

        self.zoom_btns = ZoomBtns(parent=self)
        self.zoom_btns.cmd_in.connect(self.img_wid.zoom_in)
        self.zoom_btns.cmd_out.connect(self.img_wid.zoom_out)
        self.zoom_btns.cmd_fit.connect(self.img_wid.zoom_reset)
        self.zoom_btns.cmd_close.connect(self.deleteLater)

        self.hide_btns()
        self.resize(ImgViewWin.width_ + 1, ImgViewWin.height_ + 1)
        self.set_title()
        self.load_thumbnail()

# SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM SYSTEM

    def set_title(self):
        text_ = os.path.basename(self.current_path)
        if self.current_thumb.rating > 0:
            text_ = f"{RATINGS[self.current_thumb.rating]} | {text_}"
        self.setWindowTitle(text_)

    def load_thumbnail(self):
        self.show_text("")
        pixmap = self.current_thumb.base_pixmap
        if pixmap:
            self.restart_img_wid(pixmap)
        else:
            t = f"{os.path.basename(self.current_path)}\n{self.loading_text}"
            self.show_text(t)
        self.load_image()

    def show_text(self, text: str):
        pixmap = QPixmap(1, 1)
        pixmap.fill(QColor(0, 0, 0))
        self.restart_img_wid(pixmap)
        # self.img_wid.setText(text)

    def restart_img_wid(self, pixmap: QPixmap):
        self.img_wid.deleteLater()
        self.img_wid = ImgWid()
        self.img_wid.mouse_moved.connect(self.show_btns)
        self.v_layout.addWidget(self.img_wid)
        self.img_wid.set_image(pixmap)

        self.zoom_btns.cmd_in.disconnect()
        self.zoom_btns.cmd_out.disconnect()
        self.zoom_btns.cmd_fit.disconnect()
        self.zoom_btns.cmd_in.connect(self.img_wid.zoom_in)
        self.zoom_btns.cmd_out.connect(self.img_wid.zoom_out)
        self.zoom_btns.cmd_fit.connect(self.img_wid.zoom_reset)

    def load_image(self):
        def fin(image_data: tuple[str, QImage]):
            src, qimage = image_data
            self.task_count -= 1
            if qimage is None:
                self.show_text(self.error_text)
            elif src == self.current_path:
                QTimer.singleShot(
                    300,
                    lambda: self.restart_img_wid(QPixmap.fromImage(qimage))
                )

        self.task_count += 1
        task_ = ReadImg(self.current_path)
        task_.sigs.finished_.connect(fin)
        UThreadPool.start(task_)


# GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI

    def hide_btns(self):
        for i in (self.prev_btn, self.next_btn, self.zoom_btns):
            if i.underMouse():
                return
        self.zoom_btns.hide()
        self.prev_btn.hide()
        self.next_btn.hide()

    def switch_img(self, offset: int):
        if self.task_count == self.task_count_limit:
            return

        try:
            current_index: int = self.urls.index(self.current_path)
        except ValueError:
            current_index: int = 0

        total_images: int = len(self.urls)
        new_index: int = (current_index + offset) % total_images
        self.current_path: str = self.urls[new_index]
        try:
            self.current_thumb.text_changed.disconnect()
            self.current_thumb: Thumb = self.url_to_wid.get(self.current_path)
            self.current_thumb.text_changed.connect(self.set_title)
        except RuntimeError:
            print("img view > switch img runtime err")
            return
        if not self.is_selection:
            self.move_to_wid.emit(self.current_thumb)
            self.move_to_url.emit(self.current_path)
        self.img_wid.setCursor(Qt.CursorShape.ArrowCursor)
        self.set_title()
        self.load_thumbnail()

    def show_btns(self):
        self.mouse_move_timer.stop()
        btn = (self.prev_btn, self.next_btn, self.zoom_btns)
        for i in btn:
            i.show()
            i.raise_()
        self.mouse_move_timer.start(2000)

    def win_info_cmd(self, src: str):
        self.win_info = InfoWin([self.current_thumb, ])
        self.win_info.center(self.window())
        self.win_info.show()


# EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS 

    def keyPressEvent(self, ev: QKeyEvent | None) -> None:
        if ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if ev.key() == Qt.Key.Key_I:
                self.win_info_cmd(self.current_path)

            elif ev.key() == Qt.Key.Key_0:
                self.img_wid.zoom_reset()

            elif ev.key() == Qt.Key.Key_Equal:
                self.img_wid.zoom_in()

            elif ev.key() == Qt.Key.Key_Minus:
                self.img_wid.zoom_out()

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

            elif ev.key() in KEY_RATING:
                rating = KEY_RATING.get(ev.key())
                data = (rating, self.current_path)
                self.new_rating.emit(data)
                self.set_title()

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

        ImgViewWin.width_ = self.width()
        ImgViewWin.height_ = self.height()

        return super().resizeEvent(a0)

    def leaveEvent(self, a0: QEvent | None) -> None:
        self.hide_btns()

    def deleteLater(self):
        ReadImg.cached_images.clear()
        self.closed.emit()
        return super().deleteLater()

    def closeEvent(self, a0):
        ReadImg.cached_images.clear()
        self.closed.emit()
        return super().closeEvent(a0)

    def contextMenuEvent(self, a0: QContextMenuEvent | None) -> None:
        urls = [self.current_path]
        names = [os.path.basename(i) for i in urls]

        menu = UMenu(parent=self)

        open_menu = ItemActions.OpenInApp(menu, urls)
        menu.addMenu(open_menu)

        menu.addSeparator()

        info = ItemActions.Info(menu)
        info.triggered.connect(lambda: self.win_info_cmd(self.current_path))
        menu.addAction(info)

        show_in_finder_action = ItemActions.RevealInFinder(menu, urls)
        menu.addAction(show_in_finder_action)

        copy_path = ItemActions.CopyPath(menu, urls)
        menu.addAction(copy_path)

        copy_name = ItemActions.CopyName(menu, names)
        menu.addAction(copy_name)

        menu.addSeparator()

        rating_menu = ItemActions.RatingMenu(menu, self.current_thumb.rating)
        rating_menu.new_rating.connect(lambda value: self.new_rating.emit((value, self.current_path)))
        menu.addMenu(rating_menu)

        menu.show_under_cursor()