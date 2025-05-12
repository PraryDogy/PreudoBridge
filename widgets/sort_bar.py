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


class GoToBtn(UFrame):
    clicked_ = pyqtSignal()
    svg_size = 14
    go_to_text = "Перейти"

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

        self.go_label = QLabel(GoToBtn.go_to_text)
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
        h_lay.setContentsMargins(2, 0, 2, 0)
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
    rearrange_thumbs = pyqtSignal()
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
        self.rearrange_thumbs.emit()

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
    open_go_win = pyqtSignal()
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
        self.go_to_frame.clicked_.connect(lambda: self.open_go_win.emit())
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
        self.slider.rearrange_thumbs.connect(self.rearrange_thumbs.emit)
        self.main_lay.addWidget(self.slider)

    def move_slider(self, value: int):
        self.slider.move_from_keyboard(value)

    def sort_menu_update(self):
        self.sort_frame.set_sort_text()

    def total_count_update(self, value: int):
        self.sort_frame.set_total_text(value)

    # def open_go_win(self, *args):
    #     """
    #     Открывает окно "Перейти к".

    #     В этом окне можно ввести путь к папке или файлу и нажать:
    #     - "Перейти" — для перехода внутри приложения;
    #     - "Finder" — для открытия пути в Finder.
    #     """
    #     self.win_go = GoToWin(self.main_win_item)
    #     self.win_go.load_st_grid.connect(self.load_st_grid.emit)
    #     self.win_go.center(self.window())
    #     self.win_go.show()