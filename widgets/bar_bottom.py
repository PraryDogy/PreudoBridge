import os
import subprocess
from datetime import datetime
from difflib import SequenceMatcher

from PyQt5.QtCore import QMimeData, QRunnable, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import (QContextMenuEvent, QDrag, QKeyEvent, QMouseEvent,
                         QPixmap)
from PyQt5.QtWidgets import (QAction, QApplication, QFrame, QGridLayout,
                             QHBoxLayout, QLabel, QLineEdit, QMenu,
                             QProgressBar, QPushButton, QVBoxLayout, QWidget)

from cfg import BLUE, FOLDER, JsonData
from signals import SignalsApp
from utils import Threads, Utils

from ._base import BaseSlider, WinMinMax
from ._thumb import Thumb
from .win_info import WinInfo

ARROW = " \U0000203A"
IMAGES = "images"

DISK_SMALL = os.path.join(IMAGES, "disk_small.png")
FOLDER_SMALL = os.path.join(IMAGES, "folder_small.png")
MAC_SMALL = os.path.join(IMAGES, "mac_small.png")
FILE_SMALL = os.path.join(IMAGES, "file_small.png")


class PathFinderThread(QRunnable):
    _finished = pyqtSignal(str)

    def __init__(self, src: str):
        super().__init__()
        self.src: str = src
        self.result: str = None
        self.volumes: list[str] = []
        self.exclude = "/Volumes/Macintosh HD/Volumes/"

    def run(self):
        self._path_finder()
        if not self.result:
            self._finished.emit("")
        elif self.result in self.volumes:
            self._finished.emit("")
        elif self.result:
            self._finished.emit(self.result)

    def _path_finder(self):
        src = os.sep + self.src.replace("\\", os.sep).strip().strip(os.sep)
        src_splited = [i for i in src.split(os.sep) if i]

        self.volumes = [
            os.path.join("/Volumes", i)
            for i in os.listdir("/Volumes")
            ]

        volumes_extra = [
            os.path.join(vol, *extra.strip().split(os.sep))
            for extra in JsonData.extra_paths
            for vol in self.volumes
            ]
        
        self.volumes.extend(volumes_extra)

        # обрезаем входящий путь каждый раз на 1 секцию с конца
        cut_paths: list = [
                os.path.join(*src_splited[:i])
                for i in range(len(src_splited) + 1)
                if src_splited[:i]
                ]

        # обрезаем каждый путь на 1 секцию с начала и прибавляем элементы из volumes
        all_posible_paths: list = []

        for p_path in sorted(cut_paths, key=len, reverse=True):
            p_path_split = [i for i in p_path.split(os.sep) if i]
            
            for share in self.volumes:
                for i in range(len(p_path_split) + 1):

                    all_posible_paths.append(
                        os.path.join(share, *p_path_split[i:])
                        )

        # из всех полученных возможных путей ищем самый подходящий существующий путь
        for i in sorted(all_posible_paths, key=len, reverse=True):
            if self.exclude in i:
                print("ignore strange folder", self.exclude)
                continue
            if os.path.exists(i):
                self.result = i
                break

        # смотрим совпадает ли последняя секция входящего и полученного пути
        tail = []

        if self.result:
            result_tail = self.result.split(os.sep)[-1]
            if src_splited[-1] != result_tail:
                try:
                    tail = src_splited[src_splited.index(result_tail) + 1:]
                except ValueError:
                    return

        # пытаемся найти секции пути, написанные с ошибкой
        for a in tail:
            dirs = [x for x in os.listdir(self.result)]

            for b in dirs:
                matcher = SequenceMatcher(None, a, b).ratio()
                if matcher >= 0.85:
                    self.result = os.path.join(self.result, b)
                    break


class WinGo(WinMinMax):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Перейти к ...")
        self.setFixedSize(290, 90)
        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 10, 10, 10)
        v_lay.setSpacing(10)
        self.setLayout(v_lay)

        self.input_wid = QLineEdit()
        self.input_wid.setPlaceholderText("Вставьте путь к файлу/папке")
        self.input_wid.setStyleSheet("padding-left: 2px;")
        self.input_wid.setFixedSize(270, 25)
        v_lay.addWidget(self.input_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        go_btn = QPushButton("Перейти")
        go_btn.setFixedWidth(130)
        go_btn.clicked.connect(self.open_path_btn_cmd)
        v_lay.addWidget(go_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def open_path_btn_cmd(self):
        path: str = self.input_wid.text()

        if not path:
            return

        path: str = os.sep + path.strip().strip(os.sep)

        if os.path.exists(path):
            SignalsApp.all.open_path.emit(path)
            self.close()
        else:
            path_thread = PathFinderThread(path)
            path_thread._finished.connect(self.finalize)
            Threads.pool.start(path_thread)
            # path_thread.start()

    def finalize(self, res: str):
        SignalsApp.all.open_path.emit(res)
        self.close()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()
        elif a0.key() == Qt.Key.Key_Return:
            self.open_path_btn_cmd()


class CustomSlider(BaseSlider):

    def __init__(self):
        super().__init__(orientation=Qt.Orientation.Horizontal, minimum=0, maximum=3)
        self.setFixedWidth(80)
        self.setValue(JsonData.pixmap_size_ind)
        self.valueChanged.connect(self.change_size)
    
    def change_size(self, value: int):
        self.setValue(value)
        JsonData.pixmap_size_ind = value
        SignalsApp.all.resize_grid.emit()


class PathLabel(QLabel):
    _open_img_view = pyqtSignal()

    def __init__(self, obj: str | Thumb, text: str):
        super().__init__(text)
        self.obj = obj
        self.setObjectName("path_label")

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:
        context_menu = QMenu(parent=self)

        if isinstance(self.obj, Thumb):
            src = self.obj.src
        else:
            src = self.obj

        view_action = QAction("Просмотр", self)
        cmd = lambda: self._open_img_view.emit()
        view_action.triggered.connect(cmd)
        context_menu.addAction(view_action)

        context_menu.addSeparator()

        info = QAction("Инфо", self)
        info.triggered.connect(self.show_info_win)
        context_menu.addAction(info)

        show_in_finder_action = QAction("Показать в Finder", self)
        show_in_finder_action.triggered.connect(self.show_in_finder)
        context_menu.addAction(show_in_finder_action)

        copy_path = QAction("Скопировать путь", self)
        copy_path.triggered.connect(self.copy_path)
        context_menu.addAction(copy_path)

        self.selected_style()
        context_menu.exec_(self.mapToGlobal(ev.pos()))
        self.default_style()

    def selected_style(self):
        self.setStyleSheet(f"#path_label {{ background: {BLUE}; border-radius: 2px; }} ")

    def default_style(self):
        self.setStyleSheet("")

    def copy_path(self):
        if isinstance(self.obj, Thumb):
            src = self.obj.src
        else:
            src = self.obj
        Utils.copy_path(src)

    def show_info_win(self):
        if isinstance(self.obj, Thumb):
            info = self.obj.get_info()
        else:
            info = self.get_info(self.obj)

        self.win_info = WinInfo(info)
        Utils.center_win(parent=Utils.get_main_win(), child=self.win_info)
        self.win_info.show()

    def get_info(self, src: str):
        try:
            stats = os.stat(src)

            date = datetime.fromtimestamp(stats.st_mtime).replace(microsecond=0)
            date: str = date.strftime("%d.%m.%Y %H:%M")

            size_ = Utils.get_folder_size_applescript(src)
            if size_ < 1000:
                f_size = f"{size_} МБ"
            else:
                size_ = round(size_ / (1024**3), 2)
                f_size = f"{size_} ГБ"

            name = "Имя***" + os.path.basename(src)
            type = "Тип***" + "Папка"
            path = "Путь***" + src
            size = "Размер***" + f_size
            date = "Изменен***" + date
            return "\n".join([name, type, path, size, date])

        except (PermissionError, FileNotFoundError) as e:
            return "Ошибка данных: нет доступка к папке"

    def show_in_finder(self):
        if isinstance(self.obj, Thumb):
            src = self.obj.src
        else:
            src = self.obj
        subprocess.call(["open", "-R", src])


class PathItem(QWidget):
    def __init__(self, obj: str | Thumb, name: str, pixmap: QPixmap):
        super().__init__()
        self.setFixedHeight(15)
        self.obj = obj

        item_layout = QHBoxLayout()
        item_layout.setContentsMargins(0, 0, 0, 0)
        item_layout.setSpacing(5)
        self.setLayout(item_layout)

        self.icon_label = QLabel()
        self.icon_label.setPixmap(pixmap)
        item_layout.addWidget(self.icon_label)
        
        self.path_label = PathLabel(obj=obj, text=name + ARROW)
        self.path_label.setMinimumWidth(15)
        item_layout.addWidget(self.path_label)

        self.mouseReleaseEvent = self.new_root
        self.path_label._open_img_view.connect(self.new_root)

        cmd_ = lambda e, w=self.path_label: self.expand_temp(wid=w)
        self.enterEvent = cmd_
        cmd_ = lambda e, w=self.path_label: self.collapse_temp(wid=w)
        self.leaveEvent = cmd_

    def expand_temp(self, wid: QLabel | PathLabel):
        wid.setFixedWidth(wid.sizeHint().width())

    def collapse_temp(self, wid: QLabel | PathLabel):
        wid.setMinimumWidth(15)
 
    def new_root(self, *args):
        if isinstance(self.obj, Thumb):
            self.obj.open_in_view.emit()
        else:
            SignalsApp.all.new_history.emit(self.obj)
            SignalsApp.all.load_standart_grid.emit(self.obj)

    def mousePressEvent(self, a0: QMouseEvent | None) -> None:
        if a0.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = a0.pos()

    def mouseMoveEvent(self, a0: QMouseEvent | None) -> None:
        if a0.button() == Qt.MouseButton.RightButton:
            return
        
        try:
            distance = (a0.pos() - self.drag_start_position).manhattanLength()
        except AttributeError:
            return

        if distance < QApplication.startDragDistance():
            return

        self.path_label.selected_style()
        self.drag = QDrag(self)
        self.mime_data = QMimeData()
        self.drag.setPixmap(self.icon_label.pixmap())
        
        if isinstance(self.obj, Thumb):
            src = self.obj.src
        else:
            src = self.obj

        url = [QUrl.fromLocalFile(src)]
        self.mime_data.setUrls(url)

        self.drag.setMimeData(self.mime_data)
        self.drag.exec_(Qt.DropAction.CopyAction)
        self.path_label.default_style()


class BarBottom(QWidget):
    def __init__(self):
        super().__init__()
        colspan = 0

        path_main_widget: QWidget = None

        self.grid_lay = QGridLayout()
        self.grid_lay.setContentsMargins(10, 5, 10, 0)
        self.grid_lay.setSpacing(5)
        self.setLayout(self.grid_lay)

        row, col, rowspan = 0, 0, 1
        path_main_widget = QWidget()
        self.grid_lay.addWidget(path_main_widget, row, col, rowspan, colspan, Qt.AlignmentFlag.AlignLeft)

        row, col, rowspan = 1, 0, 1
        sep = QFrame()
        sep.setStyleSheet("background: rgba(0, 0, 0, 0.2)")
        sep.setFixedHeight(1)
        self.grid_lay.addWidget(sep, row, col, rowspan, colspan)

        self.path_lay = QHBoxLayout()
        self.path_lay.setContentsMargins(0, 0, 0, 0)
        self.path_lay.setSpacing(5)
        path_main_widget.setLayout(self.path_lay)

        row, col = 2, 0

        self.go_btn = QLabel(parent=self, text=">")
        self.go_btn.setFixedSize(15, 15)
        self.go_btn.mouseReleaseEvent = self.open_go_win
        self.grid_lay.addWidget(self.go_btn, row, col)

        col += 1
        colspan += 1
        self.total = QLabel()
        self.total.setFixedHeight(15)
        self.grid_lay.addWidget(self.total, row, col, Qt.AlignmentFlag.AlignLeft)

        col += 1
        colspan += 1
        self.progressbar = QProgressBar()
        self.progressbar.setFixedSize(100, 10)
        self.grid_lay.addWidget(self.progressbar, row, col)

        col += 1
        colspan += 1
        h_spacer = QWidget()
        h_spacer.setFixedSize(10, 15)
        self.grid_lay.addWidget(h_spacer, row, col)

        col += 1
        colspan += 1
        self.slider = CustomSlider()
        self.slider.setFixedSize(70, 15)
        self.grid_lay.addWidget(self.slider, row, col)

        self.q_folder_small: QPixmap = self.small_icon(FOLDER_SMALL)
        self.q_disk_small: QPixmap = self.small_icon(DISK_SMALL)
        self.q_mac_small: QPixmap = self.small_icon(MAC_SMALL)

        SignalsApp.all.progressbar_value.connect(self.progressbar_value)
        SignalsApp.all.create_path_labels.connect(self.create_path_labels)

    def open_go_win(self, *args):
        self.win = WinGo()
        Utils.center_win(Utils.get_main_win(), self.win)
        self.win.show()

    def small_icon(self, obj: str | QPixmap):
        if isinstance(obj, str):
            return QPixmap(obj).scaled(15, 15, transformMode=Qt.TransformationMode.SmoothTransformation)
        else:
            return obj.scaled(15, 15, transformMode=Qt.TransformationMode.SmoothTransformation)

    def progressbar_value(self, value: int):
        if isinstance(value, int):
            self.progressbar.setValue(value)
        elif value == "hide":
            self.progressbar.hide()
        elif value == "show":
            self.progressbar.show()
        else:
            raise Exception("bar_borrom > progress bar wrong value", value)

    def create_path_labels(self, obj: Thumb | str, count: int | None):
        Utils.clear_layout(self.path_lay)

        # self.total.setText("Загрузка")

        if isinstance(obj, Thumb):
            root = os.path.dirname(obj.src)
        else:
            root = obj

        root = root.strip(os.sep).split(os.sep)
        path_items: list[PathItem] = []

        for x, name in enumerate(root, start=1):
            src = os.path.join(os.sep, *root[:x])
            path_item = PathItem(src, name, self.q_folder_small)
            path_items.append(path_item)
            self.path_lay.addWidget(path_item)

        path_items[0].icon_label.setPixmap(self.q_mac_small)

        if len(path_items) > 1:
            path_items[1].icon_label.setPixmap(self.q_disk_small)

        if isinstance(obj, Thumb):
            if obj.type_ != FOLDER:
                pixmap = self.small_icon(obj.img)
            else:
                pixmap = self.q_folder_small
            path_item = PathItem(obj, obj.name, pixmap)
            self.path_lay.addWidget(path_item)
            path_items.append(path_item)

        last = path_items[-1].path_label
        last.setText(last.text().replace(ARROW, ""))

        if count is not None:
            self.total.setText("Всего: " + str(count))