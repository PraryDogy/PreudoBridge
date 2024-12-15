import os
from difflib import SequenceMatcher

from PyQt5.QtCore import (QMimeData, QObject, QPoint, Qt, QTimer, QUrl,
                          pyqtSignal)
from PyQt5.QtGui import (QContextMenuEvent, QDrag, QKeyEvent, QMouseEvent,
                         QPixmap)
from PyQt5.QtWidgets import (QApplication, QFrame, QGridLayout, QHBoxLayout,
                             QLabel, QMenu, QPushButton, QSizePolicy,
                             QSpacerItem, QVBoxLayout, QWidget)

from cfg import Dynamic, JsonData, Static, ThumbData
from database import ORDER
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from ._actions import CopyPath, Info, RevealInFinder, SortMenu, View
from ._base import OpenWin, ULineEdit, USlider, USvgWidget, WinMinMax

ARROW = " \U0000203A"

SORT_T = "сортировка"
TOTAL_T = "Всего"
ASC = "по убыв."
# ASC = "\u2B23"
DESC = "по возр."
# DESC = "\u2B21"
GO_T = "Перейти"

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
        try:
            self._path_finder()
            if not self.result:
                self.signals_.finished_.emit("")
            elif self.result in self.volumes:
                self.signals_.finished_.emit("")
            elif self.result:
                self.signals_.finished_.emit(self.result)

        except RuntimeError as e:
            Utils.print_error(parent=None, error=e)

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
            self.task_ = PathFinderThread(path)
            self.task_.signals_.finished_.connect(self.finalize)
            UThreadPool.start(self.task_)

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
        super().__init__(
            orientation=Qt.Orientation.Horizontal,
            minimum=0,
            maximum=len(ThumbData.PIXMAP_SIZE) - 1
        )
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
    min_wid = 5

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
        self.collapse()
        item_layout.addWidget(self.text_wid)

    def add_arrow(self):
        t = self.text_wid.text() + ARROW
        self.text_wid.setText(t)

    def expand(self):
        self.text_wid.setFixedWidth(self.text_wid.sizeHint().width())
 
    def view_(self, *args):
        if os.path.isfile(self.src):
            OpenWin.view(Utils.get_main_win(), self.src)
        else:
            SignalsApp.all_.new_history.emit(self.src)
            SignalsApp.all_.load_normal_mode.emit(self.src)

    def solid_style(self):
        self.text_wid.setStyleSheet(
            f"""
                background: {Static.BLUE};
                border-radius: 2px;
            """
        )

    def default_style(self):
        self.text_wid.setStyleSheet("")

    def collapse(self):
        if not self.text_wid.underMouse():
            self.text_wid.setMinimumWidth(self.min_wid)

    def enterEvent(self, a0):
        self.expand()

    def leaveEvent(self, a0):
        QTimer.singleShot(500, self.collapse)

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

        self.solid_style()
        self.drag = QDrag(self)
        self.mime_data = QMimeData()

        if os.path.isfile(self.src):
            self.drag.setPixmap(QPixmap(Static.IMG_SVG))
        else:
            self.drag.setPixmap(QPixmap(Static.FOLDER_SVG))
        
        url = [QUrl.fromLocalFile(self.src)]
        self.mime_data.setUrls(url)

        self.drag.setMimeData(self.mime_data)
        self.drag.exec_(Qt.DropAction.CopyAction)
        self.default_style()

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


class GoToWid(QFrame):
    clicked_ = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFixedHeight(15)

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(2, 0, 2, 0)
        h_lay.setSpacing(5)
        self.setLayout(h_lay)

        self.go_btn = USvgWidget(src=Static.GOTO_SVG, size=13)
        h_lay.addWidget(self.go_btn)

        self.go_label = QLabel(text=GO_T)
        h_lay.addWidget(self.go_label)

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        self.clicked_.emit()


class BarBottom(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(50)
        self.current_path: str = None

        self.main_lay = QVBoxLayout()
        self.main_lay.setContentsMargins(10, 0, 10, 0)
        self.main_lay.setSpacing(0)
        self.setLayout(self.main_lay)

        # 1 строка виджет с путями
        self.create_path_labels(JsonData.root)

        # 2 строка сепаратор
        sep = QFrame()
        sep.setStyleSheet("background: rgba(0, 0, 0, 0.2)")
        sep.setFixedHeight(1)
        self.main_lay.addWidget(sep)

        # 3 строка: перейти, всего, сортировка, слайдер

        bottom_wid = QWidget()
        bottom_lay = QHBoxLayout()
        bottom_lay.setContentsMargins(0, 0, 0, 0)
        bottom_wid.setLayout(bottom_lay)
        self.main_lay.addWidget(bottom_wid)

        self.go_to_wid = GoToWid()
        self.go_to_wid.clicked_.connect(self.open_go_win)
        bottom_lay.addWidget(self.go_to_wid)

        bottom_lay.addSpacerItem(self.get_h_spacer())

        self.total_text = QLabel()
        bottom_lay.addWidget(self.total_text)

        self.sort_wid = QLabel()
        self.sort_wid.mouseReleaseEvent = self.sort_menu
        bottom_lay.addWidget(self.sort_wid)

        bottom_lay.addSpacerItem(self.get_h_spacer())

        self.slider = CustomSlider()
        self.slider.setFixedSize(70, 15)
        bottom_lay.addWidget(self.slider)

        SignalsApp.all_._path_labels_cmd.connect(self.path_labels_cmd)

    def get_h_spacer(self):
        return QSpacerItem(
            0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

    def sort_menu(self, *args):
        menu = SortMenu(parent=self.sort_wid)

        widget_top_left = self.sort_wid.rect().topLeft()

        menu_top_left = self.sort_wid.mapToGlobal(
            widget_top_left) - QPoint(0, menu.sizeHint().height()
        )
        menu.move(menu_top_left)

        menu.show()

    def add_total(self, value: int):
        self.total_text.setText(f"{TOTAL_T}: {str(value)};")

    def add_sort(self):
        sort_type = ORDER.get(JsonData.sort).get("text").lower()
        rev = ASC if JsonData.reversed else DESC
        self.sort_wid.setText(f"{SORT_T}: {sort_type} ({rev})")

    def open_go_win(self, *args):
        self.win = WinGo()
        Utils.center_win(Utils.get_main_win(), self.win)
        self.win.show()

    def path_labels_cmd(self, data: dict):

        if data.get("src"):
            self.create_path_labels(data.get("src"))

        if data.get("total"):
            self.add_total(value=data.get("total"))

        self.add_sort()

    def create_path_labels(self, src: str):

        if src == self.current_path:
            return
    
        self.current_path = src

        if hasattr(self, "path_wid"):
            self.path_wid.deleteLater()

        self.path_wid = QWidget()
        self.main_lay.insertWidget(
            0,
            self.path_wid,
            alignment=Qt.AlignmentFlag.AlignLeft
        )

        self.path_lay = QHBoxLayout()
        self.path_lay.setContentsMargins(0, 0, 0, 0)
        self.path_lay.setSpacing(5)
        self.path_wid.setLayout(self.path_lay)

        root = src.strip(os.sep).split(os.sep)

        for x, name in enumerate(root, start=1):

            src = os.path.join(os.sep, *root[:x])
            path_item = PathItem(src, name)

            if x == 1:
                icon = Static.COMP_SVG
                path_item.add_arrow()

            elif x == 2:
                icon = Static.HDD_SVG
                path_item.add_arrow()

            elif x == len(root):
                if os.path.isdir(src):
                    icon = Static.FOLDER_SVG
                else:
                    icon = Static.IMG_SVG

                # последний элемент показывать в полный размер
                path_item.expand()

                # отключаем функции схлопывания и развертывания
                path_item.enterEvent = lambda *args, **kwargs: None
                path_item.leaveEvent = lambda *args, **kwargs: None

            else:
                icon = Static.FOLDER_SVG
                path_item.add_arrow()

            path_item.img_wid.load(icon)

            self.path_lay.addWidget(path_item)
