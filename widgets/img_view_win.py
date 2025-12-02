import os

from PyQt5.QtCore import QEvent, QPointF, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import (QContextMenuEvent, QCursor, QImage, QKeyEvent,
                         QMouseEvent, QPixmap, QResizeEvent)
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QApplication, QFrame, QGraphicsPixmapItem,
                             QGraphicsScene, QGraphicsView, QHBoxLayout,
                             QLabel, QSpacerItem, QVBoxLayout, QWidget)

from cfg import Static
from system.tasks import ReadImg, UThreadPool

from ._base_widgets import UMenu, USvgSqareWidget, WinBase
from .actions import ItemActions
from .grid import KEY_RATING, RATINGS, Thumb


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
            self.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
            self.is_zoomed = False
            self.setCursor(Qt.CursorShape.ArrowCursor)

    # ---------------------- Drag через мышь ----------------------
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.ClosedHandCursor)
            self._last_mouse_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        self.mouse_moved.emit()
        if self._last_mouse_pos and event.buttons() & Qt.LeftButton:
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
        if event.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            event.ignore()  # передаём событие родителю
            return
        # для остальных клавиш можно оставить стандартную обработку
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.pixmap_item:
            self.fitInView(self.pixmap_item, Qt.KeepAspectRatio)


class UserSvg(USvgSqareWidget):
    def __init__(self, src, size):
        super().__init__(src, size)
        self.value = None


class ZoomBtns(QFrame):
    zoom_close = pyqtSignal()
    zoom_in = pyqtSignal()
    zoom_out = pyqtSignal()
    zoom_fit = pyqtSignal()

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("""
            background-color: rgba(128, 128, 128, 0.5);
            border-radius: 15px;
        """)

        h_layout = QHBoxLayout(self)
        h_layout.setSpacing(10)
        h_layout.setContentsMargins(5, 0, 5, 0)

        def add_btn(name, val):
            btn = UserSvg(os.path.join(Static.app_icons_dir, name), 45)
            btn.value = val
            h_layout.addWidget(btn)
            return btn

        add_btn("zoom_out.svg", -1)
        add_btn("zoom_in.svg", 1)
        add_btn("zoom_fit.svg", 0)
        add_btn("zoom_close.svg", 9999)

        self.mappings = {
            -1: self.zoom_out.emit,
            1: self.zoom_in.emit,
            0: self.zoom_fit.emit,
            9999: self.zoom_close.emit
        }

        self.start_pos = None
        self.is_move = False
        self.adjustSize()

    def mousePressEvent(self, e):
        self.start_pos = e.pos()
        self.is_move = False
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if not self.start_pos:
            return

        dx = e.x() - self.start_pos.x()
        if abs(dx) > 30:  # горизонтальное движение
            self.is_move = True
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            if dx > 0:
                self.zoom_in.emit()
            else:
                self.zoom_out.emit()
            self.start_pos = e.pos()
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        if self.is_move:
            self.is_move = False
            return  # не считаем клик, если двигали мышь
        pos = e.globalPos()
        wid = QApplication.widgetAt(pos)
        if isinstance(wid, UserSvg):
            func = self.mappings.get(wid.value)
            if func:
                func()
        super().mouseReleaseEvent(e)


class SwitchImgBtn(QFrame):
    pressed = pyqtSignal()

    def __init__(self, src: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(54, 54)

        self.v_layout = QVBoxLayout()
        self.v_layout.setContentsMargins(0, 0, 0, 0)
        self.v_layout.setSpacing(0)
        self.setLayout(self.v_layout)

        btn = USvgSqareWidget(src, 50)
        self.v_layout.addWidget(btn)

    def mouseReleaseEvent(self, a0):
        self.pressed.emit()
        return super().mouseReleaseEvent(a0)


class PrevImgBtn(SwitchImgBtn):
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(os.path.join(Static.app_icons_dir, "prev.svg"), parent)


class NextImgBtn(SwitchImgBtn):
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(os.path.join(Static.app_icons_dir, "next.svg"), parent)


class ImgViewWin(WinBase):
    task_count_limit = 10
    move_to_wid = pyqtSignal(object)
    move_to_url = pyqtSignal(str)
    new_rating = pyqtSignal(tuple)
    closed = pyqtSignal()
    info_win = pyqtSignal(list)
    object_name = "win_img_view"
    loading_text = "Загрузка"
    error_text = "Ошибка чтения изображения."
    min_w, min_h = 400, 300
    ww, hh = 0, 0
    xx, yy = 0, 0

    def __init__(self, start_url: str, url_to_wid: dict[str, Thumb], is_selection: bool):
        super().__init__()
        self.setMinimumSize(QSize(self.min_w, self.min_h))
        self.setObjectName(self.object_name)
        self.setStyleSheet(
            f"""#{self.object_name} {{background: black}}"""
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
        self.centralWidget().setLayout(self.v_layout)

        self.img_wid = ImgWid(QPixmap())
        self.img_wid.mouse_moved.connect(self.show_btns)
        self.v_layout.addWidget(self.img_wid)

        self.prev_btn = PrevImgBtn(self)
        self.prev_btn.pressed.connect(lambda: self.switch_img(-1))

        self.next_btn = NextImgBtn(self)
        self.next_btn.pressed.connect(lambda: self.switch_img(1))

        self.zoom_btns = ZoomBtns(parent=self)
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
        text_ = os.path.basename(self.current_path)
        if self.current_thumb.rating > 0:
            text_ = f"{RATINGS[self.current_thumb.rating]} | {text_}"
        self.setWindowTitle(text_)

    def load_thumbnail(self):
        self.set_title()
        self.text_label.hide()
        pixmap = self.current_thumb.base_pixmap
        if pixmap:
            self.restart_img_wid(pixmap)
        else:
            t = f"{os.path.basename(self.current_path)}\n{self.loading_text}"
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

    def load_image(self):
        def fin(image_data: tuple[str, QImage]):
            src, qimage = image_data
            self.task_count -= 1
            if qimage is None:
                self.show_text_label(self.error_text)
            elif src == self.current_path:
                self.restart_img_wid(QPixmap.fromImage(qimage))
        self.task_count += 1
        task_ = ReadImg(self.current_path)
        task_.sigs.finished_.connect(fin)
        UThreadPool.start(task_)


# GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI GUI

    def hide_btns(self):
        btns = (self.prev_btn, self.next_btn, self.zoom_btns)
        widget_under_cursor = QApplication.widgetAt(QCursor.pos())
        if isinstance(widget_under_cursor, QSvgWidget):
            return
        for i in btns:
            i.hide()

    def switch_img(self, offset: int):
        if self.task_count == self.task_count_limit:
            return
        if self.current_path in self.urls:
            current_index = self.urls.index(self.current_path)
        else:
            current_index = 0
        total_images = len(self.urls)
        new_index = (current_index + offset) % total_images
        self.current_path = self.urls[new_index]
        try:
            self.current_thumb.text_changed.disconnect()
            self.current_thumb = self.url_to_wid[self.current_path]
            self.current_thumb.text_changed.connect(self.set_title)
            if not self.is_selection:
                self.move_to_wid.emit(self.current_thumb)
                self.move_to_url.emit(self.current_path)
            self.load_thumbnail()
        except Exception as e:
            print("widgets ImgViewWin error", e)

    def show_btns(self):
        self.mouse_move_timer.stop()
        btn = (self.prev_btn, self.next_btn, self.zoom_btns)
        for i in btn:
            i.show()
        self.mouse_move_timer.start(2000)

    def win_info_cmd(self, src: str):
        self.info_win.emit([self.current_thumb, ])


# EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS EVENTS 

    def keyPressEvent(self, ev: QKeyEvent | None) -> None:
        if ev.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if ev.key() == Qt.Key.Key_I:
                self.win_info_cmd(self.current_path)

            elif ev.key() == Qt.Key.Key_0:
                self.img_wid.zoom_fit()

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

        ImgViewWin.ww = a0.size().width()
        ImgViewWin.hh = a0.size().height()
        ImgViewWin.xx = self.x()
        ImgViewWin.yy = self.y()

        self.text_label.resize(self.size())
        self.setFocus()

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