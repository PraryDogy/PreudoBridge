import os
import subprocess
from datetime import datetime
from difflib import SequenceMatcher

from PyQt5.QtCore import QMimeData, QObject, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import (QContextMenuEvent, QDrag, QKeyEvent, QMouseEvent,
                         QPixmap)
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QAction, QApplication, QFrame, QGridLayout,
                             QHBoxLayout, QLabel, QLineEdit, QMenu,
                             QProgressBar, QPushButton, QVBoxLayout, QWidget)

from cfg import (BLUE, COMP_SVG, FOLDER_TYPE, FOLDER_SVG, GOTO_SVG, HDD_SVG,
                 IMG_SVG, MAX_VAR, JsonData)
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from ._base import USlider, WinMinMax
from .win_info import WinInfo

ARROW = " \U0000203A"


class WorkerSignals(QObject):
    _finished = pyqtSignal(str)


class PathFinderThread(URunnable):

    def __init__(self, src: str):
        super().__init__()
        self.worker_signals = WorkerSignals()
        self.src: str = src
        self.result: str = None
        self.volumes: list[str] = []
        self.exclude = "/Volumes/Macintosh HD/Volumes/"

    def run(self):
        self._path_finder()
        if not self.result:
            self.worker_signals._finished.emit("")
        elif self.result in self.volumes:
            self.worker_signals._finished.emit("")
        elif self.result:
            self.worker_signals._finished.emit(self.result)

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
            path_thread.worker_signals._finished.connect(self.finalize)
            UThreadPool.pool.start(path_thread)

    def finalize(self, res: str):
        SignalsApp.all.open_path.emit(res)
        self.close()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()
        elif a0.key() == Qt.Key.Key_Return:
            self.open_path_btn_cmd()


class CustomSlider(USlider):
    def __init__(self):
        super().__init__(orientation=Qt.Orientation.Horizontal, minimum=0, maximum=MAX_VAR)
        self.setFixedWidth(80)
        self.setValue(JsonData.pixmap_size_ind)
        self.valueChanged.connect(self.change_size)
        SignalsApp.all.move_slider.connect(self.change_size)
    
    def change_size(self, value: int):
        self.setValue(value)
        JsonData.pixmap_size_ind = value
        SignalsApp.all.resize_grid.emit()


class PathLabel(QLabel):
    _open_img_view = pyqtSignal()

    def __init__(self, src: str, text: str):
        super().__init__(text)
        self.src = src
        self.setObjectName("path_label")

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:
        context_menu = QMenu(parent=self)

        view_action = QAction("Просмотр", self)
        cmd = lambda: self._open_img_view.emit()
        view_action.triggered.connect(cmd)
        context_menu.addAction(view_action)

        context_menu.addSeparator()

        info = QAction("Инфо", self)
        info.triggered.connect(self.show_info_win)
        context_menu.addAction(info)

        cmd_ = lambda: subprocess.call(["open", "-R", self.src])
        show_in_finder_action = QAction("Показать в Finder", self)
        show_in_finder_action.triggered.connect(cmd_)
        context_menu.addAction(show_in_finder_action)

        copy_path = QAction("Скопировать путь", self)
        copy_path.triggered.connect(lambda: Utils.copy_path(self.src))
        context_menu.addAction(copy_path)

        self.selected_style()
        context_menu.exec_(self.mapToGlobal(ev.pos()))
        self.default_style()

    def selected_style(self):
        self.setStyleSheet(f"#path_label {{ background: {BLUE}; border-radius: 2px; }} ")

    def default_style(self):
        self.setStyleSheet("")

    def show_info_win(self):
        self.win_info = WinInfo(self.src)
        Utils.center_win(parent=Utils.get_main_win(), child=self.win_info)
        self.win_info.show()

    def show_in_finder(self):
        subprocess.call(["open", "-R", self.src])


class PathItem(QWidget):
    def __init__(self, src: str, name: str):
        super().__init__()
        self.setFixedHeight(15)
        self.src = src

        item_layout = QHBoxLayout()
        item_layout.setContentsMargins(0, 0, 0, 0)
        item_layout.setSpacing(5)
        self.setLayout(item_layout)

        flag_ = Qt.AspectRatioMode.KeepAspectRatioByExpanding
        self.img_wid = QSvgWidget()
        self.img_wid.renderer().setAspectRatioMode(flag_)
        self.img_wid.setFixedSize(15, 15)

        item_layout.addWidget(self.img_wid)
        
        self.path_label = PathLabel(src=src, text=name)
        self.path_label.setMinimumWidth(15)
        item_layout.addWidget(self.path_label)

        self.mouseReleaseEvent = self.view_
        self.path_label._open_img_view.connect(self.view_)

        cmd_ = lambda e, w=self.path_label: self.expand_temp(wid=w)
        self.enterEvent = cmd_
        cmd_ = lambda e, w=self.path_label: self.collapse_temp(wid=w)
        self.leaveEvent = cmd_

    def add_arrow(self):
        t = self.path_label.text() + ARROW
        self.path_label.setText(t)

    def expand_temp(self, wid: QLabel | PathLabel):
        wid.setFixedWidth(wid.sizeHint().width())

    def collapse_temp(self, wid: QLabel | PathLabel):
        wid.setMinimumWidth(15)
 
    def view_(self, *args):
        if os.path.isfile(self.src):
            from .win_img_view import WinImgView
            self.win_ = WinImgView(self.src)
            Utils.center_win(parent=Utils.get_main_win(), child=self.win_)
            self.win_.show()
        else:
            SignalsApp.all.new_history.emit(self.src)
            SignalsApp.all.load_standart_grid.emit(self.src)

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

        if os.path.isfile(self.src):
            self.drag.setPixmap(QPixmap(IMG_SVG))
        else:
            self.drag.setPixmap(QPixmap(FOLDER_SVG))
        
        url = [QUrl.fromLocalFile(self.src)]
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

        self.go_btn = QSvgWidget()
        self.go_btn.load(GOTO_SVG)
        self.go_btn.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
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

        SignalsApp.all.progressbar_cmd.connect(self.progressbar_cmd)
        SignalsApp.all.path_labels_cmd.connect(self.path_labels_cmd)

    def open_go_win(self, *args):
        self.win = WinGo()
        Utils.center_win(Utils.get_main_win(), self.win)
        self.win.show()

    def progressbar_cmd(self, cmd: int | str):
        if isinstance(cmd, int):
            self.progressbar.setValue(cmd)
        elif cmd == "hide":
            self.progressbar.hide()
        elif cmd == "show":
            self.progressbar.show()
        elif "max " in cmd:
            value = int(cmd.split(" ")[-1])
            self.progressbar.setMaximum(value)
        else:
            raise Exception("bar_borrom > progress bar wrong cmd", cmd)
        
    def path_labels_cmd(self, data: dict):

        if data.get("src"):
            self.create_path_labels(data.get("src"))

        if data.get("total"):
            self.total.setText("Всего: " + str(data.get("total")))

    def create_path_labels(self, src: str):
        Utils.clear_layout(self.path_lay)

        root = src.strip(os.sep).split(os.sep)
        ln = len(root)
        path_items: list[PathItem] = []

        for x, name in enumerate(root, start=1):

            src = os.path.join(os.sep, *root[:x])
            path_item = PathItem(src, name)

            if x == 1:
                icon = COMP_SVG
                path_item.add_arrow()
            elif x == 2:
                icon = HDD_SVG
                path_item.add_arrow()
            elif x == ln:
                if os.path.isdir(src):
                    icon = FOLDER_SVG
                else:
                    icon = IMG_SVG
            else:
                icon = FOLDER_SVG
                path_item.add_arrow()

            path_item.img_wid.load(icon)
            path_items.append(path_item)
            self.path_lay.addWidget(path_item)

        # if isinstance(obj, Thumb):
        #     path_item = PathItem(obj, obj.name, IMG_SVG)
        #     self.path_lay.addWidget(path_item)
        #     path_items.append(path_item)

        # last = path_items[-1]
        # last.path_label.setText(last.path_label.text().replace(ARROW, ""))

        # if isinstance(last.path_label.obj, ThumbFolder):
            # last.img_wid.load(FOLDER_SVG)

        # if count is not None:
        #     self.total.setText("Всего: " + str(count))