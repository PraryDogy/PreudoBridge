import os
import subprocess

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeyEvent, QMouseEvent
from PyQt5.QtWidgets import QFrame, QGridLayout, QWidget

from cfg import FOLDER_TYPE, GRID_SPACING, MAX_VAR, Dymanic, JsonData
from database import OrderItem
from signals import SignalsApp
from utils import Utils

from ._base import GridBase
from ._thumb import Thumb, ThumbFolder, ThumbSearch
from .win_img_view import PathToWid


class Grid(GridBase):

    def __init__(self, width: int):
        super().__init__()
        self.setWidgetResizable(True)

        self.curr_cell: tuple = (0, 0)
        self.cell_to_wid: dict[tuple, Thumb] = {}
        self.ordered_widgets: list[OrderItem | Thumb | ThumbFolder | ThumbSearch] = []
        PathToWid.all_.clear()

        self.ww = width

        # Посколько сетка может множество раз перезагружаться
        # прежде нужно отключить прошлые подключения чтобы не было
        # дублирования подклювчений
        SignalsApp.disconnect_grid()

        SignalsApp.all.resize_grid.connect(self.resize_)
        SignalsApp.all.sort_grid.connect(self.order_)
        SignalsApp.all.filter_grid.connect(self.filter_)
        SignalsApp.all.move_to_wid.connect(self.select_new_widget)

        main_wid = QWidget()
        self.grid_layout = QGridLayout(main_wid)
        self.grid_layout.setSpacing(GRID_SPACING)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setWidget(main_wid)

    def select_new_widget(self, data: tuple | str | Thumb):
        if isinstance(data, Thumb):
            coords = data.row, data.col
            new_wid = data

        elif isinstance(data, tuple):
            coords = data
            new_wid = self.cell_to_wid.get(data)

        elif isinstance(data, str):
            new_wid = PathToWid.all_.get(data)
            coords = new_wid.row, new_wid.col

        prev_wid = self.cell_to_wid.get(self.curr_cell)

        if isinstance(new_wid, Thumb):
            prev_wid.set_no_frame()
            new_wid.set_frame()
            self.curr_cell = coords
            self.ensureWidgetVisible(new_wid)
            SignalsApp.all.path_labels_cmd.emit(new_wid.src)
        else:
            try:
                prev_wid.set_frame()
            except AttributeError:
                pass

        self.setFocus()

    def reset_selection(self):
        widget = self.cell_to_wid.get(self.curr_cell)

        if isinstance(widget, QFrame):
            widget.set_no_frame()
            self.curr_cell: tuple = (0, 0)
    
    def set_rating(self, rating: int):
        rating_data = {48: 0, 49: 1, 50: 2, 51: 3, 52: 4, 53: 5}
        wid: Thumb = self.cell_to_wid.get(self.curr_cell)

        if isinstance(wid, Thumb):
            wid.set_rating_cmd(rating_data.get(rating))
            self.select_new_widget(self.curr_cell)

    def order_(self):
        self.ordered_widgets = OrderItem.order_items(self.ordered_widgets)
        
        PathToWid.all = {
            wid.src: wid
            for wid in self.ordered_widgets
            if isinstance(wid, Thumb)
            }
        
        self.rearrange()

    def filter_(self):
        for wid in self.ordered_widgets:
            show_widget = True

            if Dymanic.rating_filter > 0:
                if not (Dymanic.rating_filter >= wid.rating > 0):
                    show_widget = False

            if Dymanic.color_filters:
                if not any(color for color in wid.colors if color in Dymanic.color_filters):
                    show_widget = False

            if show_widget:
                wid.must_hidden = False
                wid.show()
            else:
                wid.must_hidden = True
                wid.hide()

        self.rearrange()

    def resize_(self):
        for wid in self.ordered_widgets:
            wid.setup()
        self.rearrange()

    def rearrange(self, width: int = None):
        # когда меняется размер окна, этот метод отвечает за перетасовку
        # виджетов, поэтому отсюда мы отсылаем в инициатор self.ww
        if width:
            self.ww = width
            col_count = Utils.get_clmn_count(width)
        else:
            col_count = Utils.get_clmn_count(self.ww)

        self.reset_selection()
        self.cell_to_wid.clear()

        row, col = 0, 0

        for wid in self.ordered_widgets:

            if wid.must_hidden:
                continue

            self.grid_layout.addWidget(wid, row, col)
            self.cell_to_wid[row, col] = wid
            wid.row, wid.col = row, col

            col += 1
            if col >= col_count:
                col = 0
                row += 1
        
    def add_widget_data(self, wid: Thumb, row: int, col: int):
        wid.row, wid.col = row, col
        self.cell_to_wid[row, col] = wid
        PathToWid.all_[wid.src] = wid
        self.ordered_widgets.append(wid)

    def open_in_view(self, wid: Thumb):
        if wid.type_ == FOLDER_TYPE:
            SignalsApp.all.new_history.emit(wid.src)
            SignalsApp.all.load_standart_grid.emit(wid.src)

        else:
            from .win_img_view import WinImgView
            self.win = WinImgView(wid.src)
            Utils.center_win(parent=Utils.get_main_win(), child=self.win)
            self.win.show()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        wid: Thumb | ThumbFolder 

        if a0.modifiers() & Qt.KeyboardModifier.ControlModifier:

            if a0.key() == Qt.Key.Key_Up:
                root = os.path.dirname(JsonData.root)
                if root != os.sep:
                    SignalsApp.all.new_history.emit(root)
                    SignalsApp.all.load_standart_grid.emit(root)

            elif  a0.key() == Qt.Key.Key_Down:
                wid = self.cell_to_wid.get(self.curr_cell)
                self.open_in_view(wid)

            elif a0.key() == Qt.Key.Key_I:
                wid = self.cell_to_wid.get(self.curr_cell)
                wid.show_info_win()

            elif a0.key() == Qt.Key.Key_Equal:
                new_value = JsonData.pixmap_size_ind + 1
                if new_value <= MAX_VAR:
                    SignalsApp.all.move_slider.emit(new_value)

            elif a0.key() == Qt.Key.Key_Minus:
                new_value = JsonData.pixmap_size_ind - 1
                if new_value >= 0:
                    SignalsApp.all.move_slider.emit(new_value)

        elif a0.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            wid = self.cell_to_wid.get(self.curr_cell)
            if wid:
                self.open_in_view(wid)

        elif a0.key() == Qt.Key.Key_Left:
            coords = (self.curr_cell[0], self.curr_cell[1] - 1)
            self.select_new_widget(coords)

        elif a0.key() == Qt.Key.Key_Right:
            coords = (self.curr_cell[0], self.curr_cell[1] + 1)
            self.select_new_widget(coords)

        elif a0.key() == Qt.Key.Key_Up:
            coords = (self.curr_cell[0] - 1, self.curr_cell[1])
            self.select_new_widget(coords)

        elif a0.key() == Qt.Key.Key_Down:
            coords = (self.curr_cell[0] + 1, self.curr_cell[1])
            self.select_new_widget(coords)

        elif a0.key() in (Qt.Key.Key_0, Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4, Qt.Key.Key_5):
            self.set_rating(a0.key())
        
        return super().keyPressEvent(a0)

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        wid = self.cell_to_wid.get(self.curr_cell)
        if isinstance(wid, Thumb):
            wid.set_no_frame()
        self.setFocus()
        SignalsApp.all.path_labels_cmd.emit(JsonData.root)