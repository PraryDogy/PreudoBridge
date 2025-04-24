import os
import subprocess

from PyQt5.QtCore import QObject, QPoint, Qt, pyqtSignal
from PyQt5.QtGui import QKeyEvent, QMouseEvent
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                             QWidget)

from cfg import Dynamic, Static, ThumbData
from utils import URunnable, UThreadPool, Utils

from ._base_items import (MinMaxDisabledWin, Sort, UFrame, ULineEdit,
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
        paths = cls.add_to_start(splited, volumes)
        res = cls.check_for_exists(paths)

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
            res = cls.check_for_exists(paths)

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


class GoToWin(MinMaxDisabledWin):
    load_st_grid_sig = pyqtSignal(tuple)

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

        self.input_wid = ULineEdit()
        self.input_wid.setPlaceholderText(GO_PLACEGOLDER)
        self.input_wid.setFixedWidth(270)
        self.input_wid.move_clear_btn()

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
        go_btn.clicked.connect(lambda: self.open_path_btn_cmd(None))
        h_lay.addWidget(go_btn)

        go_finder_btn = QPushButton(FINDER_T)
        go_finder_btn.setFixedWidth(120)
        go_finder_btn.clicked.connect(
            lambda: self.open_path_btn_cmd(FINDER_T)
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
            self.open_finder(result)
        else:
            if os.path.isfile(result):
                main_dir = os.path.dirname(result)
                select_path = result
            else:
                main_dir = result
                select_path = None
            self.load_st_grid_sig.emit((main_dir, select_path))
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


class GoToBtn(UFrame):
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

        self.go_btn = USvgSqareWidget(Static.GOTO_SVG, 14)
        h_lay.addWidget(self.go_btn)

        self.go_label = QLabel(text=GO_T)
        h_lay.addWidget(self.go_label)

        self.adjustSize()

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        if a0.button() == Qt.MouseButton.LeftButton:
            self.clicked_.emit()


class SortMenuBtn(UFrame):
    sort_grid_sig = pyqtSignal()
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

    def set_sort_text(self):
        """
        Отображает текст на основе типа сортировки, например:   
        Сортировка: имя (по возраст.)
        """
        # получаем текстовое имя сортировки на основе внутреннего имени сортировки
        sort_ = Sort.items.get(Dynamic.sort)
        sort_ = sort_.lower()

        # получаем текстовое имя обратной или прямой сортировки
        rev = ASC if Dynamic.rev else DESC

        self.sort_wid.setText(f"{SORT_T}: {sort_} ({rev})")

    def set_total_text(self, value: int):
        """
        Отображает общее число виджетов в сетке
        """
        self.total_text.setText(f"{TOTAL_T}: {str(value)}")

    def mouseReleaseEvent(self, a0: QMouseEvent):
        """
        При клике на выбранный пункт меню произойдет:
        - Обновится нижний бар
        - Сортировка сетки
        - Перетасовка сетки
        """
        menu_ = SortMenu(self)
        menu_.sort_grid_sig.connect(self.sort_grid_sig.emit)
        menu_.rearrange_grid_sig.connect(self.rearrange_grid_sig.emit)
        menu_.sort_bar_update_sig.connect(self.set_sort_text)

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
        Обрабатывает изменение слайдера при его перемещении мышью.
        Обновляет размер виджетов и инициирует перетасовку сетки.
        """
        Dynamic.pixmap_size_ind = value
        self.resize_grid_sig.emit()
        self.rearrange_grid_sig.emit()

    def move_from_keyboard(self, value: int):
        """
        Обрабатывает изменение слайдера при нажатии Cmd+ или Cmd-.
        Вызывает `setValue`, что автоматически обновляет размер виджетов
        и сетки через `move_slider_cmd`.
        """
        self.setValue(value)


class SortBar(QWidget):
    load_st_grid_sig = pyqtSignal(tuple)
    sort_grid_sig = pyqtSignal()
    resize_grid_sig = pyqtSignal()
    rearrange_grid_sig = pyqtSignal()

    def __init__(self):
        """
        Состав:

        - Кнопка "Перейти" — открывает окно "Перейти к";
        - Кнопка "Всего виджетов / Тип сортировки" — открывает меню сортировки;
        - Слайдер — изменяет размер виджетов в сетке.
        """

        super().__init__()
        self.setFixedHeight(25)
        self.main_lay = QHBoxLayout()
        self.main_lay.setContentsMargins(0, 0, 10, 0)
        self.main_lay.setSpacing(5)
        self.setLayout(self.main_lay)

        self.go_to_frame = GoToBtn()
        self.go_to_frame.clicked_.connect(self.open_go_win)
        self.main_lay.addWidget(self.go_to_frame)

        self.main_lay.addStretch()

        self.sort_frame = SortMenuBtn()
        self.sort_frame.sort_grid_sig.connect(self.sort_grid_sig.emit)
        self.sort_frame.rearrange_grid_sig.connect(self.rearrange_grid_sig.emit)
        self.main_lay.addWidget(self.sort_frame)

        self.main_lay.addStretch()

        self.slider = CustomSlider()
        self.slider.resize_grid_sig.connect(self.resize_grid_sig.emit)
        self.slider.rearrange_grid_sig.connect(self.rearrange_grid_sig.emit)
        self.slider.setFixedSize(70, 15)
        self.main_lay.addWidget(self.slider)

    def setup(self, value: int | None):
        """
        SortFrame содержит два виджета: "Тип сортировки" и "Количество виджетов в сетке".

        - value — значение для виджета "Количество виджетов в сетке". Может быть None.
        - При вызове этого метода всегда обновляется виджет "Тип сортировки".
        - Если value — целое число, также обновляется виджет "Количество виджетов в сетке".
        """

        self.sort_frame.set_sort_text()
        if isinstance(value, int):
            self.sort_frame.set_total_text(value)

    def open_go_win(self, *args):
        """
        Открывает окно "Перейти к".

        В этом окне можно ввести путь к папке или файлу и нажать:
        - "Перейти" — для перехода внутри приложения;
        - "Finder" — для открытия пути в Finder.
        """
        self.win_go = GoToWin()
        self.win_go.load_st_grid_sig.connect(self.load_st_grid_sig.emit)
        self.win_go.center(self.window())
        self.win_go.show()