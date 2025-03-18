import os
import subprocess

from PyQt5.QtCore import (QMimeData, QObject, QPoint, Qt, QTimer, QUrl,
                          pyqtSignal)
from PyQt5.QtGui import (QContextMenuEvent, QDrag, QKeyEvent, QMouseEvent,
                         QPixmap)
from PyQt5.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
                             QPushButton, QVBoxLayout, QWidget, QAction)

from cfg import Dynamic, JsonData, Static, ThumbData
from database import ORDER
from signals import SignalsApp
from utils import PathFinder, URunnable, UThreadPool, Utils

from ._actions import CopyPath, Info, RevealInFinder, SortMenu, View
from ._base import (OpenWin, UFrame, ULineEdit, UMenu, USlider, USvgWidget,
                    WinMinMax)
from ._grid import Thumb

SORT_T = "Сортировка"
TOTAL_T = "Всего"
ASC = "по убыв."
DESC = "по возр."
GO_T = "Перейти"
CURR_WID = "curr_wid"
FINDER_T = "Finder"
GO_PLACEGOLDER = "Вставьте путь к файлу/папке"
ARROW_RIGHT = " \U0000203A" # ›


class WorkerSignals(QObject):
    finished_ = pyqtSignal(str)


class PathFinderThread(URunnable):

    def __init__(self, src: str):
        super().__init__()
        self.signals_ = WorkerSignals()
        self.src: str = src

    @URunnable.set_running_state
    def run(self):
        try:
            result = PathFinder.get_result(path=self.src)

            if not result:
                self.signals_.finished_.emit("")
            
            else:
                self.signals_.finished_.emit(result)

        except RuntimeError as e:
            Utils.print_error(parent=None, error=e)


class GoLineEdit(ULineEdit):
    ww = 270

    def __init__(self):
        super().__init__()
        self.setPlaceholderText(GO_PLACEGOLDER)
        self.setFixedWidth(GoLineEdit.ww)
        self.clear_btn_vcenter()

    def clicked_(self, text: str):
        self.clear()
        self.setText(text)
        QTimer.singleShot(10, self.deselect)

    def mouseDoubleClickEvent(self, a0):

        menu = UMenu(parent=self)

        for i in Dynamic.go_paths:
            action_ = QAction(parent=menu, text=i)
            action_.triggered.connect(lambda e, tt=i: self.clicked_(text=tt))
            menu.addAction(action_)
        
        menu.exec_(self.mapToGlobal(self.rect().bottomLeft()))

        return super().mouseDoubleClickEvent(a0)


class WinGo(WinMinMax):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Перейти к ...")
        self.setFixedSize(290, 90)
        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 10, 10, 10)
        v_lay.setSpacing(10)
        self.setLayout(v_lay)

        self.input_wid = GoLineEdit()
        v_lay.addWidget(self.input_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        h_wid = QWidget()
        v_lay.addWidget(h_wid)

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)
        h_wid.setLayout(h_lay)

        h_lay.addStretch()

        go_btn = QPushButton(GO_T)
        go_btn.setFixedWidth(120)
        go_btn.clicked.connect(
            lambda: self.open_path_btn_cmd(flag=None)
        )
        h_lay.addWidget(go_btn)

        go_finder_btn = QPushButton(FINDER_T)
        go_finder_btn.setFixedWidth(120)
        go_finder_btn.clicked.connect(
            lambda: self.open_path_btn_cmd(flag=FINDER_T)
        )
        h_lay.addWidget(go_finder_btn)

        h_lay.addStretch()

        clipboard = Utils.read_from_clipboard()
        task = PathFinderThread(src=clipboard)
        task.signals_.finished_.connect(self.first_load_final)
        UThreadPool.start(runnable=task)

    def first_load_final(self, result: str | None):
        if result:
            self.input_wid.setText(result)

    def open_path_btn_cmd(self, flag: str):
        path: str = self.input_wid.text()
        task = PathFinderThread(src=path)
        task.signals_.finished_.connect(
            lambda result: self.finalize(result=result, flag=flag)
        )
        UThreadPool.start(runnable=task)

        if path not in Dynamic.go_paths:
            Dynamic.go_paths.append(path)

    def finalize(self, result: str, flag: str):

        if not result:
            self.close()
            return

        if flag == FINDER_T:
            self.open_finder(dest=result)

        else:
            SignalsApp.instance.open_path.emit(result)

        self.close()

    def open_finder(self, dest: str):
        try:
            subprocess.Popen(["open", "-R", dest])
        except Exception as e:
            print(e)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()


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
        SignalsApp.instance.move_slider.connect(self.change_size)
    
    def change_size(self, value: int):
        # отключаем сигнал valueChanged
        self.blockSignals(True)
        self.setValue(value)

        # Включаем сигнал обратно
        self.blockSignals(False)
        Dynamic.pixmap_size_ind = value
        SignalsApp.instance.resize_grid.emit()


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
        t = self.text_wid.text() + " " + ARROW_RIGHT
        self.text_wid.setText(t)

    def expand(self):
        self.text_wid.setFixedWidth(self.text_wid.sizeHint().width())
 
    def view_(self, *args):
        if os.path.isfile(self.src):
            OpenWin.view(Utils.get_main_win(), self.src)
        else:
            SignalsApp.instance.new_history_item.emit(self.src)
            SignalsApp.instance.load_standart_grid_cmd(
                path=self.src,
                prev_path=None
            )

    def solid_style(self):
        self.text_wid.setStyleSheet(
            f"""
                background: {Static.BLUE_GLOBAL};
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
        menu = UMenu(parent=self)

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


class GoToFrame(UFrame):
    clicked_ = pyqtSignal()

    def __init__(self):
        super().__init__()

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(2, 2, 2, 2)
        h_lay.setAlignment(
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft
        )
        h_lay.setSpacing(5)
        self.setLayout(h_lay)

        self.go_btn = USvgWidget(src=Static.GOTO_SVG, size=14)
        h_lay.addWidget(self.go_btn)

        self.go_label = QLabel(text=GO_T)
        h_lay.addWidget(self.go_label)

        self.adjustSize()

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        self.clicked_.emit()


class SortFrame(UFrame):
    def __init__(self):
        super().__init__()
        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(2, 0, 2, 0)
        self.setLayout(h_lay)

        self.total_text = QLabel()
        h_lay.addWidget(self.total_text)

        self.sort_wid = QLabel()
        h_lay.addWidget(self.sort_wid)

    def add_sort(self):
        # получаем текстовое имя сортировки на основе внутреннего имени сортировки
        order = ORDER.get(Dynamic.sort)
        order = order.lower()

        # получаем текстовое имя обратной или прямой сортировки
        rev = ASC if Dynamic.rev else DESC

        self.sort_wid.setText(f"{SORT_T}: {order} ({rev})")

    def mouseReleaseEvent(self, a0: QMouseEvent):

        menu_ = SortMenu(parent=self)

        widget_rect = self.rect()
        menu_size = menu_.sizeHint()

        centered = QPoint(
            menu_size.width() // 2,
            menu_size.height() + self.height() // 2
        )

        menu_center_top = self.mapToGlobal(widget_rect.center()) - centered

        menu_.move(menu_center_top)
        menu_.exec_()
        super().leaveEvent(a0=a0)


class BarBottom(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(50)
        self.setAcceptDrops(True)
        self.current_path: str = None
        self.path_item_list: list[PathItem] = []

        self.main_lay = QVBoxLayout()
        self.main_lay.setContentsMargins(10, 0, 10, 0)
        self.main_lay.setSpacing(0)
        self.setLayout(self.main_lay)

        # 1 строка виджет с путями
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

        # 2 строка сепаратор
        sep = QFrame()
        sep.setStyleSheet("background: rgba(0, 0, 0, 0.2)")
        sep.setFixedHeight(1)
        self.main_lay.addWidget(sep)

        # 3 строка: перейти, всего, сортировка, слайдер

        bottom_wid = QWidget()
        bottom_lay = QHBoxLayout()
        bottom_lay.setContentsMargins(0, 0, 0, 0)
        bottom_lay.setSpacing(10)
        bottom_wid.setLayout(bottom_lay)
        self.main_lay.addWidget(bottom_wid)

        self.go_to_frame = GoToFrame()
        self.go_to_frame.clicked_.connect(self.open_go_win)
        bottom_lay.addWidget(self.go_to_frame)

        bottom_lay.addStretch()

        self.sort_frame = SortFrame()
        bottom_lay.addWidget(self.sort_frame)

        bottom_lay.addStretch()

        self.slider = CustomSlider()
        self.slider.setFixedSize(70, 15)
        bottom_lay.addWidget(self.slider)

        self.create_path_labels(JsonData.root)
        SignalsApp.instance.bar_bottom_cmd.connect(self.path_labels_cmd)

    def add_total(self, value: int):
        self.sort_frame.total_text.setText(f"{TOTAL_T}: {str(value)}")

    def open_go_win(self, *args):
        self.win = WinGo()
        Utils.center_win(Utils.get_main_win(), self.win)
        self.win.show()

    def path_labels_cmd(self, data: dict):

        if data.get("src"):
            self.create_path_labels(data.get("src"))

        if data.get("total"):
            self.add_total(value=data.get("total"))
        self.sort_frame.add_sort()

    def create_path_labels(self, src: str):

        if src == self.current_path:
            return

        for i in self.path_item_list:
            i.deleteLater()

        self.path_item_list.clear()

        self.current_path = src
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

            self.path_item_list.append(path_item)
            path_item.img_wid.load(icon)
            self.path_lay.addWidget(path_item)
