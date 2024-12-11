import os
from difflib import SequenceMatcher

from PyQt5.QtCore import QEvent, QMimeData, QObject, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import (QContextMenuEvent, QDrag, QKeyEvent, QMouseEvent,
                         QPixmap)
from PyQt5.QtWidgets import (QApplication, QFrame, QGridLayout, QHBoxLayout,
                             QLabel, QMenu, QPushButton, QSizePolicy,
                             QVBoxLayout, QWidget, QSpacerItem)

from cfg import (BLUE, COMP_SVG, FOLDER_SVG, GOTO_SVG, GRAY_SLIDER, HDD_SVG, IMG_SVG,
                 MAX_VAR, Dynamic, JsonData)
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from ._actions import CopyPath, Info, RevealInFinder, View
from ._base import OpenWin, ULineEdit, USlider, USvgWidget, WinMinMax

ARROW = " \U0000203A"


class WorkerSignals(QObject):
    finished_ = pyqtSignal(str)


class PathFinderThread(URunnable):

    def __init__(self, src: str):
        super().__init__()
        self.signals_ = WorkerSignals()
        self.src: str = src
        self.result: str = None
        self.volumes: list[str] = []
        self.exclude = "/Volumes/Macintosh HD/Volumes/"

    @URunnable.set_running_state
    def run(self):
        self._path_finder()
        if not self.result:
            self.signals_.finished_.emit("")
        elif self.result in self.volumes:
            self.signals_.finished_.emit("")
        elif self.result:
            self.signals_.finished_.emit(self.result)

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

        self.input_wid = ULineEdit()
        self.input_wid.setPlaceholderText("Вставьте путь к файлу/папке")
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
            SignalsApp.all_.open_path.emit(path)
            self.close()
        else:
            path_thread = PathFinderThread(path)
            path_thread.signals_.finished_.connect(self.finalize)
            UThreadPool.start(path_thread)

    def finalize(self, res: str):
        SignalsApp.all_.open_path.emit(res)
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
        self.setValue(Dynamic.pixmap_size_ind)
        self.valueChanged.connect(self.change_size)
        SignalsApp.all_.move_slider.connect(self.change_size)
    
    def change_size(self, value: int):
        # отключаем сигнал valueChanged
        self.blockSignals(True)
        self.setValue(value)

        # Включаем сигнал обратно
        self.blockSignals(False)
        Dynamic.pixmap_size_ind = value
        SignalsApp.all_.resize_grid.emit()


class PathItem(QWidget):

    def __init__(self, src: str, name: str):
        super().__init__()
        self.setFixedHeight(15)
        self.src = src

        item_layout = QHBoxLayout()
        item_layout.setContentsMargins(0, 0, 0, 0)
        item_layout.setSpacing(5)
        self.setLayout(item_layout)

        self.img_wid = USvgWidget(size=15)

        item_layout.addWidget(self.img_wid)
        
        self.text_wid = QLabel(text=name)
        self.text_wid.setMinimumWidth(15)
        item_layout.addWidget(self.text_wid)

    def add_arrow(self):
        t = self.text_wid.text() + ARROW
        self.text_wid.setText(t)

    def expand(self):
        self.text_wid.setFixedWidth(self.text_wid.sizeHint().width())

    def collapse(self):
        self.text_wid.setMinimumWidth(5)
 
    def view_(self, *args):
        if os.path.isfile(self.src):
            OpenWin.view(Utils.get_main_win(), self.src)

        else:
            SignalsApp.all_.new_history.emit(self.src)
            SignalsApp.all_.load_standart_grid.emit(self.src)

    def solid_style(self):
        self.text_wid.setStyleSheet(
            f"""
                background: {BLUE};
                border-radius: 2px;
            """
        )

    def default_style(self):
        self.text_wid.setStyleSheet("")

    def enterEvent(self, a0):
        self.expand()

    def leaveEvent(self, a0):
        self.collapse()

    def mouseReleaseEvent(self, a0):
        self.view_()

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

        self.text_wid.selected_style()
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
        self.text_wid.default_style()

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:
        menu = QMenu(parent=self)

        view_action = View(menu, self.src)
        view_action._clicked.connect(self.view_)
        menu.addAction(view_action)

        menu.addSeparator()

        info = Info(menu, self.src)
        menu.addAction(info)

        show_in_finder_action = RevealInFinder(menu, self.src)
        menu.addAction(show_in_finder_action)

        copy_path = CopyPath(menu, self.src)
        menu.addAction(copy_path)

        self.solid_style()
        menu.exec_(self.mapToGlobal(ev.pos()))
        self.default_style()


class Total(QFrame):
    clicked_ = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("total")
        self.setFixedHeight(15)

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(2, 0, 2, 0)
        self.setLayout(h_lay)

        self.go_btn = USvgWidget(src=GOTO_SVG, size=13)
        h_lay.addWidget(self.go_btn)

        self.total_text = QLabel()
        h_lay.addWidget(self.total_text)

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        self.clicked_.emit()

    def enterEvent(self, a0: QEvent | None) -> None:
        self.setStyleSheet(
            f"""
            #total {{
                background: {GRAY_SLIDER};
                border-radius: 3px;
            }}
            """
        )
    
    def leaveEvent(self, a0: QEvent | None) -> None:
        self.setStyleSheet("")


class BarBottom(QWidget):
    def __init__(self):
        super().__init__()

        # потому что в 3 строке 3 виджета: тотал, распорка, слайдер
        colspan = 3

        # 1 строка # 1 строка # 1 строка # 1 строка # 1 строка # 1 строка

        grid_lay = QGridLayout()
        grid_lay.setContentsMargins(10, 5, 10, 0)
        grid_lay.setSpacing(5)
        self.setLayout(grid_lay)

        row, col, rowspan = 0, 0, 1
        path_wid = QWidget()
        grid_lay.addWidget(
            path_wid,
            row, col,
            rowspan, colspan,
            Qt.AlignmentFlag.AlignLeft
        )

        self.path_lay = QHBoxLayout()
        self.path_lay.setContentsMargins(0, 0, 0, 0)
        self.path_lay.setSpacing(5)
        path_wid.setLayout(self.path_lay)

        # 2 строка, разделительная линия # 2 строка, разделительная линия

        row, col, rowspan = 1, 0, 1
        sep = QFrame()
        sep.setStyleSheet("background: rgba(0, 0, 0, 0.2)")
        sep.setFixedHeight(1)
        grid_lay.addWidget(sep, row, col, rowspan, colspan)


        # 2 строка, "всего" + "перейти" # 2 строка, "всего" + "перейти"

        row, col = 2, 0
        self.total = Total()
        self.total.clicked_.connect(self.open_go_win)
        grid_lay.addWidget(self.total, row, col)

        row, col = 2, 1
        spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding)
        grid_lay.addItem(spacer, row, col)

        row, col = 2, 2
        self.slider = CustomSlider()
        self.slider.setFixedSize(70, 15)
        grid_lay.addWidget(self.slider, row, col)

        SignalsApp.all_.path_labels_cmd.connect(self.path_labels_cmd)

    def open_go_win(self, *args):
        self.win = WinGo()
        Utils.center_win(Utils.get_main_win(), self.win)
        self.win.show()

    def path_labels_cmd(self, data: dict):

        if data.get("src"):
            self.create_path_labels(data.get("src"))

        if data.get("total"):
            self.total.total_text.setText("Всего: " + str(data.get("total")))

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

                path_item.expand()

            else:
                icon = FOLDER_SVG
                path_item.add_arrow()

            path_item.img_wid.load(icon)
            path_items.append(path_item)
            self.path_lay.addWidget(path_item)
