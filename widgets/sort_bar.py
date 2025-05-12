import os
import subprocess

from PyQt5.QtCore import QObject, QPoint, Qt, pyqtSignal
from PyQt5.QtGui import QKeyEvent, QMouseEvent
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                             QWidget)

from cfg import Dynamic, Static, ThumbData
from utils import Utils

from ._base_items import (MainWinItem, MinMaxDisabledWin, SortItem, UFrame,
                          ULineEdit, URunnable, USlider, USvgSqareWidget,
                          UThreadPool)
from .actions import SortMenu

GO_TO_TEXT = "Перейти"
FINDER_TEXT = "Finder"


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

    def task(self):
        result = PathFinder.get_result(self.src)
        if not result:
            result = ""
        try:
            self.signals_.finished_.emit(result)
        except RuntimeError as e:
            Utils.print_error(e)


class GoToWin(MinMaxDisabledWin):
    load_st_grid_sig = pyqtSignal()
    placeholder_text = "Вставьте путь к файлу/папке"
    title_text = "Перейти к ..."
    input_width = 270

    def __init__(self, main_win_item: MainWinItem):
        """
        Окно перейти:
        - поле ввода
        - кнопка "Перейти" - переход к директории внутри приложения, отобразится
        новая сетка с указанным путем
        - кнопка "Finder" - путь откроется в Finder
        """
        super().__init__()
        self.set_modality()
        self.main_win_item = main_win_item
        self.setWindowTitle(GoToWin.title_text)
        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(5, 5, 5, 5)
        v_lay.setSpacing(5)
        self.setLayout(v_lay)

        self.input_wid = ULineEdit()
        self.input_wid.setPlaceholderText(GoToWin.placeholder_text)
        self.input_wid.setFixedWidth(GoToWin.input_width)

        v_lay.addWidget(self.input_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        h_wid = QWidget()
        v_lay.addWidget(h_wid)

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)
        h_wid.setLayout(h_lay)

        h_lay.addStretch()

        go_btn = QPushButton(GO_TO_TEXT)
        go_btn.setFixedWidth(100)
        go_btn.clicked.connect(lambda: self.open_path_btn_cmd(None))
        h_lay.addWidget(go_btn)

        go_finder_btn = QPushButton(FINDER_TEXT)
        go_finder_btn.setFixedWidth(100)
        go_finder_btn.clicked.connect(
            lambda: self.open_path_btn_cmd(FINDER_TEXT)
        )
        h_lay.addWidget(go_finder_btn)

        h_lay.addStretch()

        self.adjustSize()

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
        task = PathFinderThread(path)
        cmd_ = lambda result: self.finalize(result, flag)
        task.signals_.finished_.connect(cmd_)
        UThreadPool.start(task)

    def finalize(self, result: str, flag: str):
        """
        - result - полученный путь из PathFinderThread
        - flag None означает переход к указанном пути внутри приложения,
        загрузится новая сетка по указанному пути
        - flag FINDER_T откроет Finder по указанному пути
        """
        if not result:
            self.deleteLater()
            return
        if flag == FINDER_TEXT:
            self.open_finder(result)
        else:
            if os.path.isfile(result):
                main_dir = os.path.dirname(result)
                self.main_win_item.go_to = result
            else:
                main_dir = result
            self.main_win_item.main_dir = main_dir
            self.load_st_grid_sig.emit()
        self.deleteLater()

    def open_finder(self, dest: str):
        """
        Открыть указанный путь в Finder
        """
        try:
            subprocess.Popen(["open", "-R", dest])
        except Exception as e:
            Utils.print_error(e)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()


class GoToBtn(UFrame):
    clicked_ = pyqtSignal()
    svg_size = 14

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

        self.go_btn = USvgSqareWidget(Static.GOTO_SVG, GoToBtn.svg_size)
        h_lay.addWidget(self.go_btn)

        self.go_label = QLabel(GO_TO_TEXT)
        h_lay.addWidget(self.go_label)

        self.adjustSize()

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        if a0.button() == Qt.MouseButton.LeftButton:
            self.clicked_.emit()


class SortFrame(UFrame):
    sort_thumbs = pyqtSignal()
    rearrange_thumbs = pyqtSignal()
    sort_text = "Сортировка"
    total_text = "Всего"
    asc_text = "по убыв."
    desc_text = "по возр."

    def __init__(self, sort_item: SortItem):
        """
        Виджет с раскрывающимся меню, которое предлагает сортировку сетки
        """
        super().__init__()
        self.sort_item = sort_item

        h_lay = QHBoxLayout()
        self.setLayout(h_lay)

        self.total_text_label = QLabel()
        h_lay.addWidget(self.total_text_label)

        self.sort_wid = QLabel()
        h_lay.addWidget(self.sort_wid)

    def set_sort_text(self):
        """
        Отображает текст на основе типа сортировки, например:   
        Сортировка: имя (по возраст.)
        """
        # получаем текстовое имя сортировки на основе внутреннего имени сортировки
        sort_ = SortItem.lang_dict.get(self.sort_item.get_sort())
        sort_ = sort_.lower()

        # получаем текстовое имя обратной или прямой сортировки
        rev = SortFrame.asc_text if self.sort_item.get_rev() else SortFrame.desc_text

        text_ = f"{SortFrame.sort_text}: {sort_} ({rev})"
        self.sort_wid.setText(text_)

    def set_total_text(self, value: int):
        """
        Отображает общее число виджетов в сетке
        """
        text_ = f"{SortFrame.total_text}: {str(value)}"
        self.total_text_label.setText(text_)

    def mouseReleaseEvent(self, a0: QMouseEvent):
        """
        При клике на выбранный пункт меню произойдет:
        - Обновится нижний бар
        - Сортировка сетки
        - Перетасовка сетки
        """
        menu_ = SortMenu(self, self.sort_item)
        menu_.sort_grid_sig.connect(self.sort_thumbs.emit)
        menu_.rearrange_grid_sig.connect(self.rearrange_thumbs.emit)
        menu_.sort_menu_update.connect(lambda: self.set_sort_text())

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
        super().leaveEvent(a0)


class CustomSlider(USlider):
    resize_thumbs = pyqtSignal()
    rearrange_grid_sig = pyqtSignal()
    width_ = 70
    height_ = 15

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
        self.setFixedSize(CustomSlider.width_, CustomSlider.height_)
        self.setValue(Dynamic.pixmap_size_ind)
        self.valueChanged.connect(self.move_slider_cmd)
    
    def move_slider_cmd(self, value: int):
        """
        Обрабатывает изменение слайдера при его перемещении мышью.
        Обновляет размер виджетов и инициирует перетасовку сетки.
        """
        Dynamic.pixmap_size_ind = value
        self.resize_thumbs.emit()
        self.rearrange_grid_sig.emit()

    def move_from_keyboard(self, value: int):
        """
        Обрабатывает изменение слайдера при нажатии Cmd+ или Cmd-.
        Вызывает `setValue`, что автоматически обновляет размер виджетов
        и сетки через `move_slider_cmd`.
        """
        self.setValue(value)


class SortBar(QWidget):
    load_st_grid = pyqtSignal()
    sort_thumbs = pyqtSignal()
    resize_thumbs = pyqtSignal()
    rearrange_thumbs = pyqtSignal()
    height_ = 25

    def __init__(self, sort_item: SortItem, main_win_item: MainWinItem):
        """
        Состав:

        - Кнопка "Перейти" — открывает окно "Перейти к";
        - Кнопка "Всего виджетов / Тип сортировки" — открывает меню сортировки;
        - Слайдер — изменяет размер виджетов в сетке.
        """

        super().__init__()
        self.setFixedHeight(SortBar.height_)
        self.sort_item = sort_item
        self.main_win_item = main_win_item

        self.init_ui()

    def init_ui(self):
        self.main_lay = self.create_main_layout()
        self.setLayout(self.main_lay)

        self.create_go_to_button()
        self.main_lay.addStretch()
        self.create_sort_button()
        self.main_lay.addStretch()
        self.create_slider()

    def create_main_layout(self):
        """Создает и настраивает основной layout"""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 10, 0)
        layout.setSpacing(5)
        return layout

    def create_go_to_button(self):
        """Создает кнопку для перехода"""
        self.go_to_frame = GoToBtn()
        self.go_to_frame.clicked_.connect(self.open_go_win)
        self.main_lay.addWidget(self.go_to_frame)

    def create_sort_button(self):
        """Создает кнопку сортировки"""
        self.sort_frame = SortFrame(self.sort_item)
        self.sort_frame.sort_thumbs.connect(self.sort_thumbs.emit)
        self.sort_frame.rearrange_thumbs.connect(self.rearrange_thumbs.emit)
        self.main_lay.addWidget(self.sort_frame)

    def create_slider(self):
        """Создает слайдер для изменения размера элементов"""
        self.slider = CustomSlider()
        self.slider.resize_thumbs.connect(self.resize_thumbs.emit)
        self.slider.rearrange_grid_sig.connect(self.rearrange_thumbs.emit)
        self.main_lay.addWidget(self.slider)

    def move_slider(self, value: int):
        self.slider.move_from_keyboard(value)

    def sort_menu_update(self):
        self.sort_frame.set_sort_text()

    def total_count_update(self, value: int):
        self.sort_frame.set_total_text(value)

    def open_go_win(self, *args):
        """
        Открывает окно "Перейти к".

        В этом окне можно ввести путь к папке или файлу и нажать:
        - "Перейти" — для перехода внутри приложения;
        - "Finder" — для открытия пути в Finder.
        """
        self.win_go = GoToWin(self.main_win_item)
        self.win_go.load_st_grid_sig.connect(self.load_st_grid.emit)
        self.win_go.center(self.window())
        self.win_go.show()