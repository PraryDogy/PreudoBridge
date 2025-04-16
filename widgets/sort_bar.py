import os
import subprocess

from PyQt5.QtCore import QObject, QPoint, Qt, pyqtSignal
from PyQt5.QtGui import QKeyEvent, QMouseEvent
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                             QWidget)

from cfg import Dynamic, Static, ThumbData
from database import ORDER_DICT
from utils import URunnable, UThreadPool, Utils

from ._base_widgets import (MinMaxDisabledWin, UFrame, ULineEdit, UMenu,
                            USlider, USvgSqareWidget)
from .actions import SortMenu

SORT_T = "Сортировка"
TOTAL_T = "Всего"
ASC = "по убыв."
DESC = "по возр."
GO_T = "Перейти"
CURR_WID = "curr_wid"
FINDER_T = "Finder"
GO_PLACEGOLDER = "Вставьте путь к файлу/папке"
ARROW_RIGHT = " \U0000203A" # ›
GO_LINE_EDIT_W = 270


class PathFinder:

    @classmethod
    def get_result(cls, path: str) -> str | None:
        path = path.strip()
        path = path.replace("\\", os.sep)
        path = path.strip("'").strip('"') # кавычки
        path = Utils.normalize_slash(path)

        # если это локальный путь начинающийся с /Users/Username, то меняем его
        # на /Volumes/Macintosh HD/Users/Username
        path = Utils.add_system_volume(path)

        if not path:
            return None

        splited = [i for i in path.split(os.sep) if i]
        volumes = [i.path for i in os.scandir(os.sep + Static.VOLUMES)]

        # см. аннотацию add_to_start
        paths = cls.add_to_start(splited_path=splited, volumes=volumes)
        res = cls.check_for_exists(paths=paths)

        if res in volumes:
            return None

        elif res:
            return res
        
        else:
            # см. аннотацию метода del_from_end
            paths = [
                ended_path
                for path_ in paths
                for ended_path in cls.del_from_end(path=path_)
            ]

            paths.sort(key=len, reverse=True)
            res = cls.check_for_exists(paths=paths)

            if res in volumes:
                return None
            
            elif res:
                return res
    
    @classmethod
    def add_to_start(cls, splited_path: list, volumes: list[str]) -> list[str]:
        """
        Пример:
        >>> splited_path = ["Volumes", "Shares-1", "Studio", "MIUZ", "Photo", "Art", "Raw", "2025"]
        >>> volumes = ["/Volumes/Shares", "/Volumes/Shares-1"]
        [
            '/Volumes/Shares/Studio/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares/Photo/Art/Raw/2025',
            '/Volumes/Shares/Art/Raw/2025',
            '/Volumes/Shares/Raw/2025',
            '/Volumes/Shares/2025',
            ...
            '/Volumes/Shares-1/Studio/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares-1/MIUZ/Photo/Art/Raw/2025',
            '/Volumes/Shares-1/Photo/Art/Raw/2025',
            ...
        ]
        """
        new_paths = []

        for vol in volumes:

            splited_path_copy = splited_path.copy()
            while len(splited_path_copy) > 0:

                new = vol + os.sep + os.path.join(*splited_path_copy)
                new_paths.append(new)
                splited_path_copy.pop(0)

        new_paths.sort(key=len, reverse=True)
        return new_paths
    
    @classmethod
    def check_for_exists(cls, paths: list[str]) -> str | None:
        for i in paths:
            if os.path.exists(i):
                return i
        return None
    
    @classmethod
    def del_from_end(cls, path: str) -> list[str]:
        """
        Пример:
        >>> path: "/sbc01/Shares/Studio/MIUZ/Photo/Art/Raw/2025"
        [
            "/sbc01/Shares/Studio/MIUZ/Photo/Art/Raw/2025",
            "/sbc01/Shares/Studio/MIUZ/Photo/Art/Raw",
            "/sbc01/Shares/Studio/MIUZ/Photo/Art",
            "/sbc01/Shares/Studio/MIUZ/Photo",
            "/sbc01/Shares/Studio/MIUZ",
            "/sbc01/Shares/Studio",
            "/sbc01/Shares",
            "/sbc01",
        ]
        """
        new_paths = []

        while path != os.sep:
            new_paths.append(path)
            path, _ = os.path.split(path)

        return new_paths
    

class WorkerSignals(QObject):
    finished_ = pyqtSignal(str)


class PathFinderThread(URunnable):
    def __init__(self, src: str):
        """
        Входящий путь к файлу папке проходит через PathFinder, корректируется
        при необходимости. Например:
        - Входящий путь /Volumes/Shares-1/file.txt
        - У отправившего пользователя есть подключенный общий диск Shares-1
        - У принявшего пользователя (нашего) диск значится как Shares-2
        - PathFinder поймет это и скорректирует путь
        - /Volumes/Shares-2/file.txt
        """
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

    def __init__(self):
        super().__init__()
        self.setPlaceholderText(GO_PLACEGOLDER)
        self.setFixedWidth(GO_LINE_EDIT_W)
        self.clear_btn_vcenter()


class WinGo(MinMaxDisabledWin):
    open_path_sig = pyqtSignal(str)

    def __init__(self):
        """
        Окно перейти:
        - поле ввода
        - кнопка "Перейти" - переход к директории внутри приложения, отобразится
        новая сетка с указанным путем
        - кнопка "Finder" - путь откроется в Finder
        """
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

        # при инициации окна пытаемся считать буфер обмена, если там есть
        # путь, то вставляем его в поле ввода
        clipboard = Utils.read_from_clipboard()
        task = PathFinderThread(src=clipboard)
        task.signals_.finished_.connect(self.first_load_final)
        UThreadPool.start(runnable=task)

    def first_load_final(self, result: str | None):
        """
        Завершение PathFinderThread при инициации окна
        """
        if result:
            self.input_wid.setText(result)

    def open_path_btn_cmd(self, flag: str):
        """
        Общий метод для кнопок "Перейти" и "Finder"
        - flag None означает переход к указанном пути внутри приложения,
        загрузится новая сетка по указанному пути
        - flag FINDER_T откроет Finder по указанному пути
        """
        path: str = self.input_wid.text()
        task = PathFinderThread(src=path)
        cmd_ = lambda result: self.finalize(result, flag)
        task.signals_.finished_.connect(cmd_)
        UThreadPool.start(runnable=task)

    def finalize(self, result: str, flag: str):
        """
        - result - полученный путь из PathFinderThread
        - flag None означает переход к указанном пути внутри приложения,
        загрузится новая сетка по указанному пути
        - flag FINDER_T откроет Finder по указанному пути
        """
        if not result:
            self.close()
            return
        if flag == FINDER_T:
            self.open_finder(dest=result)
        else:
            self.open_path_sig.emit(result)
        self.close()

    def open_finder(self, dest: str):
        """
        Открыть указанный путь в Finder
        """
        try:
            subprocess.Popen(["open", "-R", dest])
        except Exception as e:
            print(e)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()


class CustomSlider(USlider):
    resize_grid_sig = pyqtSignal()
    rearrange_grid_sig = pyqtSignal()

    def __init__(self):
        """
        Слайдер с пользовательским стилем
        - 4 позиции
        - каждая позиция отвечает за свой размер виджета сетки
        - при смене позиции слайдера произойзет изменение размеров виджетов сетки
        и перетасовка с учетом новых размеров:
        изменится число столбцов и строк в сетке
        """
        super().__init__(
            orientation=Qt.Orientation.Horizontal,
            minimum=0,
            maximum=len(ThumbData.PIXMAP_SIZE) - 1
        )
        self.setFixedWidth(80)
        self.setValue(Dynamic.pixmap_size_ind)
        self.valueChanged.connect(self.move_slider_cmd)
    
    def move_slider_cmd(self, value: int):
        """
        Перемещение слайдера происходит:
        - При клике мыши (valueChanged)
        - При нажатии cmd + и cmd -
        - Чтобы действие не задваивалось, сначала отключается сигнал valueChanged,
        затем происходит изменение размеров сетки и обратное подключение сетки
        """
        # отключаем сигнал valueChanged
        self.blockSignals(True)
        self.setValue(value)

        # Включаем сигнал обратно
        self.blockSignals(False)
        Dynamic.pixmap_size_ind = value
        self.resize_grid_sig.emit()
        self.rearrange_grid_sig.emit()


class GoToFrame(UFrame):
    clicked_ = pyqtSignal()

    def __init__(self):
        """
        Виджет, который открывает окно "Перейти", чтобы перейти к файлу / папке
        внутри приложения или в Finder
        """
        super().__init__()

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(2, 2, 2, 2)
        h_lay.setAlignment(
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft
        )
        h_lay.setSpacing(5)
        self.setLayout(h_lay)

        self.go_btn = USvgSqareWidget(src=Static.GOTO_SVG, size=14)
        h_lay.addWidget(self.go_btn)

        self.go_label = QLabel(text=GO_T)
        h_lay.addWidget(self.go_label)

        self.adjustSize()

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        if a0.button() == Qt.MouseButton.LeftButton:
            self.clicked_.emit()


class SortFrame(UFrame):
    bar_bottom_update = pyqtSignal(tuple)
    order_grid_sig = pyqtSignal()
    rearrange_grid_sig = pyqtSignal()

    def __init__(self):
        """
        Виджет с раскрывающимся меню, которое предлагает сортировку сетки
        """
        super().__init__()
        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(2, 0, 2, 0)
        self.setLayout(h_lay)

        self.total_text = QLabel()
        h_lay.addWidget(self.total_text)

        self.sort_wid = QLabel()
        h_lay.addWidget(self.sort_wid)

    def setup(self):
        """
        Отображает текст на основе типа сортировки, например:   
        Сортировка: имя (по возраст.)
        """
        # получаем текстовое имя сортировки на основе внутреннего имени сортировки
        order = ORDER_DICT.get(Dynamic.sort)
        order = order.lower()

        # получаем текстовое имя обратной или прямой сортировки
        rev = ASC if Dynamic.rev else DESC

        self.sort_wid.setText(f"{SORT_T}: {order} ({rev})")

    def mouseReleaseEvent(self, a0: QMouseEvent):
        """
        При клике на выбранный пункт меню произойдет:
        - Обновится нижний бар
        - Сортировка сетки
        - Перетасовка сетки
        """
        menu_ = SortMenu(parent=self)
        menu_.order_grid_sig.connect(self.order_grid_sig.emit)
        menu_.rearrange_grid_sig.connect(self.rearrange_grid_sig)

        widget_rect = self.rect()
        menu_size = menu_.sizeHint()

        centered = QPoint(
            menu_size.width() // 2,
            menu_size.height() + self.height() // 2
        )

        # меню всплывает точно над данным виджетом
        menu_center_top = self.mapToGlobal(widget_rect.center()) - centered
        menu_.move(menu_center_top)
        menu_.exec_()
        super().leaveEvent(a0=a0)


class SortBar(QWidget):
    def __init__(self):
        super().__init__()

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
        self.sort_frame.bar_bottom_update.connect(self.update_bar_cmd)
        self.sort_frame.order_grid_sig.connect(self.order_grid_sig.emit)
        self.sort_frame.rearrange_grid_sig.connect(self.rearrange_grid_sig.emit)
        bottom_lay.addWidget(self.sort_frame)

        bottom_lay.addStretch()

        self.slider = CustomSlider()
        self.slider.resize_grid_sig.connect(self.resize_grid_sig.emit)
        self.slider.rearrange_grid_sig.connect(self.rearrange_grid_sig.emit)
        self.slider.setFixedSize(70, 15)
        bottom_lay.addWidget(self.slider)

    def add_total(self, value: int):
        """
        Отображает общее число виджетов в сетке
        """
        self.sort_frame.total_text.setText(f"{TOTAL_T}: {str(value)}")


    def open_go_win(self, *args):
        """
        Открывает окно "перейти к"  
        В окне можно вставить путь к папке файлу и нажать "Перейти" или "Finder"    
        В первом случае будет переход внутри приложения, во втором откроется Finder
        """
        self.win_go = WinGo()
        self.win_go.open_path_sig.connect(self.open_path_sig.emit)
        self.win_go.center(self.window())
        self.win_go.show()