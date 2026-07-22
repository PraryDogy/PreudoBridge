import os

from PyQt6.QtCore import (QCoreApplication, QEvent, QPoint, Qt, QTimer,
                          pyqtSignal)
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from cfg import Dynamic, Static
from system.items import MainWinItem, SortItem, TotalCountItem

from ._base_widgets import BaseSignals, HoverGrayLabel, UFrame, USlider
from .actions import Menus


class BarSortFrame(UFrame):
    def __init__(self):
        super().__init__()



class GoToBtn(UFrame):
    clicked_ = pyqtSignal()
    go_to_text = "Перейти"
    icon_path = os.path.join(Static.internal_images_dir, "go_to.svg")
    icon_size = 14

    def __init__(self):
        super().__init__()

        h_lay = QHBoxLayout(self)
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        h_lay.setSpacing(4)

        self.go_btn = QSvgWidget()
        self.go_btn.load(self.icon_path)
        self.go_btn.setFixedSize(self.icon_size, self.icon_size)
        h_lay.addWidget(self.go_btn)

        self.go_label = HoverGrayLabel(self.go_to_text)
        self.go_label.set_text_size(11)
        h_lay.addWidget(self.go_label)

        self.adjustSize()

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        if a0.button() == Qt.MouseButton.LeftButton:
            self.clicked_.emit()

    def enterEvent(self, event: QEvent):
        enter_event = QEvent(QEvent.Type.Enter)
        QCoreApplication.sendEvent(self.go_label, enter_event)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent):
        leave_event = QEvent(QEvent.Type.Leave)
        QCoreApplication.sendEvent(self.go_label, leave_event)
        super().leaveEvent(event)


class SortFrame(UFrame):
    sort_grid = pyqtSignal()
    rearrange_grid = pyqtSignal()
    sort_text = "Сортировка"
    total_text = "Всего"
    asc_text = "по убыв."
    desc_text = "по возр."

    def __init__(self, main_win_item: MainWinItem):
        super().__init__()
        self.main_win_item = main_win_item

        h_lay = QHBoxLayout(self)
        h_lay.setContentsMargins(2, 0, 2, 0)

        self.total_text_label = HoverGrayLabel("")
        self.total_text_label.set_text_size(11)
        h_lay.addWidget(self.total_text_label)

        self.sort_wid = HoverGrayLabel("")
        self.sort_wid.set_text_size(11)
        h_lay.addWidget(self.sort_wid)

    def set_sort_text(self):
        """
        Отображает текст на основе типа сортировки, например:   
        Сортировка: имя (по возраст.)
        """
        # получаем текстовое имя сортировки на основе внутреннего имени сортировки
        sort_ = SortItem.attr_lang.get(self.main_win_item.sort_item.item_type)
        sort_ = sort_.lower()

        # получаем текстовое имя обратной или прямой сортировки
        rev = SortFrame.asc_text if self.main_win_item.sort_item.reversed else SortFrame.desc_text

        text_ = f"{SortFrame.sort_text}: {sort_} ({rev})"
        self.sort_wid.setText(text_)

    def set_total_text(self, item: TotalCountItem):
        if item.selected > 0:
            text_ = f"Выбрано {item.selected} из {item.total}"
        else:
            text_ = f"{self.total_text}: {str(item.total)}"
        QTimer.singleShot(10, lambda: self.total_text_label.setText(text_))

    def sort_menu_triggered(self):
        self.sort_grid.emit(),
        self.rearrange_grid.emit(),
        self.set_sort_text()

    def mouseReleaseEvent(self, a0: QMouseEvent):
        """
        При клике на выбранный пункт меню произойдет:
        - Обновится нижний бар
        - Сортировка сетки
        - Перетасовка сетки
        """
        menus = Menus(None, self.main_win_item)
        menus.sort_menu.triggered.connect(self.sort_menu_triggered)

        widget_rect = self.rect()
        menu_size = menus.sort_menu.sizeHint()

        centered = QPoint(
            menu_size.width() // 2,
            menu_size.height() + self.height() // 2
        )

        # меню всплывает точно над данным виджетом
        menu_center_top = self.mapToGlobal(widget_rect.center()) - centered
        menus.sort_menu.move(menu_center_top)
        menus.sort_menu.exec()
        super().leaveEvent(a0)

    def enterEvent(self, event: QEvent):
        enter_event = QEvent(QEvent.Type.Enter)
        QCoreApplication.sendEvent(self.total_text_label, enter_event)
        QCoreApplication.sendEvent(self.sort_wid, enter_event)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent):
        leave_event = QEvent(QEvent.Type.Leave)
        QCoreApplication.sendEvent(self.total_text_label, leave_event)
        QCoreApplication.sendEvent(self.sort_wid, leave_event)
        super().leaveEvent(event)
        

class CustomSlider(USlider):
    resize_grid = pyqtSignal()
    rearrange_grid = pyqtSignal()
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
            maximum=len(Static.pixmap_sizes) - 1
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
        self.resize_grid.emit()
        self.rearrange_grid.emit()

    def move_from_keyboard(self, value: int):
        """
        Обрабатывает изменение слайдера при нажатии Cmd+ или Cmd-.
        Вызывает `setValue`, что автоматически обновляет размер виджетов
        и сетки через `move_slider_cmd`.
        """
        self.setValue(value)


class BarSort(QWidget):
    sort_grid = pyqtSignal()
    go_to_win_open = pyqtSignal()
    height_ = 25

    def __init__(self, main_win_item: MainWinItem):
        """
        Состав:

        - Кнопка "Перейти" — открывает окно "Перейти к";
        - Кнопка "Всего виджетов / Тип сортировки" — открывает меню сортировки;
        - Слайдер — изменяет размер виджетов в сетке.
        """

        super().__init__()
        self.setFixedHeight(BarSort.height_)
        self.main_win_item = main_win_item
        self.base_signals = BaseSignals()
        self.init_ui()
        self.sort_menu_update()

    def init_ui(self):
        self.main_lay = self.create_main_layout()

        self.create_go_to_button()
        self.main_lay.addStretch()
        self.create_sort_button()

        self.main_lay.addStretch()
        self.create_slider()

    def create_main_layout(self):
        """Создает и настраивает основной layout"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 10, 0)
        layout.setSpacing(5)
        return layout

    def create_go_to_button(self):
        """Создает кнопку для перехода"""
        self.go_to_frame = GoToBtn()
        self.go_to_frame.clicked_.connect(lambda: self.go_to_win_open.emit())
        self.main_lay.addWidget(self.go_to_frame)

    def create_sort_button(self):
        """Создает кнопку сортировки"""
        self.sort_frame = SortFrame(self.main_win_item)
        self.sort_frame.sort_grid.connect(self.sort_grid.emit)
        self.sort_frame.rearrange_grid.connect(self.base_signals.rearrange_grid.emit)
        self.main_lay.addWidget(self.sort_frame)

    def create_slider(self):
        """Создает слайдер для изменения размера элементов"""
        self.slider = CustomSlider()
        self.slider.resize_grid.connect(self.base_signals.resize_grid.emit)
        self.slider.rearrange_grid.connect(self.base_signals.rearrange_grid.emit)
        self.main_lay.addWidget(self.slider)

    def move_slider(self, value: int):
        self.slider.move_from_keyboard(value)

    def sort_menu_update(self):
        self.sort_frame.set_sort_text()