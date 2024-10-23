import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeyEvent, QMouseEvent
from PyQt5.QtWidgets import QFrame, QGridLayout, QWidget

from cfg import GRID_SPACING, Config, JsonData
from utils import Utils

from ._base import BaseGrid
from ._thumb import Thumb, ThumbFolder, ThumbSearch


class Grid(BaseGrid):

    def __init__(self):
        super().__init__()

        self.curr_cell: tuple = (0, 0)
        self.cell_to_wid: dict[tuple, Thumb] = {}
        self.path_to_wid: dict[str, Thumb] = {}
        self.sorted_widgets: list[Thumb | ThumbFolder | ThumbSearch] = []

        self.setWidgetResizable(True)

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
            new_wid = self.path_to_wid.get(data)
            coords = new_wid.row, new_wid.col

        if isinstance(new_wid, Thumb):
            prev_wid = self.cell_to_wid.get(self.curr_cell)
            prev_wid.set_no_frame()
            new_wid.set_frame()
            self.curr_cell = coords
            self.ensureWidgetVisible(new_wid)

    def reset_selection(self):
        widget = self.cell_to_wid.get(self.curr_cell)

        if isinstance(widget, QFrame):
            widget.set_no_frame()
            self.curr_cell: tuple = (0, 0)
    
    def set_rating(self, rating: int):
        rating_data = {48: 0, 49: 1, 50: 2, 51: 3, 52: 4, 53: 5}
        wid: Thumb = self.cell_to_wid.get(self.curr_cell)
        if isinstance(wid, Thumb):
            if wid.update_data_db(wid.colors, rating_data.get(rating)):
                wid.set_rating_from_db(rating_data.get(rating))
                self.select_new_widget(self.curr_cell)

    def sort_grid(self, width: int):
        if not self.sorted_widgets:
            return

        if not hasattr(Thumb("", 0, 0, {}), JsonData.sort):
            print("_grid.py > sort_grid > Thumb не имеет атрибута из JsonData.sort")
            quit()

        if JsonData.sort == "colors":
            key = lambda x: len(getattr(x, JsonData.sort))
        else:
            key = lambda x: getattr(x, JsonData.sort)
        rev = JsonData.reversed
        self.sorted_widgets = sorted(self.sorted_widgets, key=key, reverse=rev)
        
        self.path_to_wid = {
            wid.src: wid
            for wid in self.sorted_widgets
            if isinstance(wid, Thumb)
            }
        
        self.rearrange_grid(width)

    def filter_grid(self, width: int):
        for wid in self.sorted_widgets:
            show_widget = True

            if Config.rating_filter > 0:
                if not (Config.rating_filter >= wid.rating > 0):
                    show_widget = False

            if Config.color_filters:
                if not any(color for color in wid.colors if color in Config.color_filters):
                    show_widget = False

            if show_widget:
                wid.must_hidden = False
                wid.show()
            else:
                wid.must_hidden = True
                wid.hide()

        self.rearrange_grid(width)

    def resize_grid(self, width: int):
        for wid in self.sorted_widgets:
            wid.resize()
            wid.resize_pixmap()
        self.rearrange_grid(width)

    def rearrange_grid(self, width: int):
        self.reset_selection()
        self.cell_to_wid.clear()

        col_count = Utils.get_clmn_count(width)
        row, col = 0, 0

        for wid in self.sorted_widgets:

            if wid.must_hidden:
                continue

            self.grid_layout.addWidget(wid, row, col)
            self.cell_to_wid[row, col] = wid
            wid.path_to_wid = self.path_to_wid
            wid.row, wid.col = row, col

            col += 1
            if col >= col_count:
                col = 0
                row += 1

    def add_widget_data(self, wid: Thumb, row: int, col: int):
        wid.row, wid.col = row, col
        self.cell_to_wid[row, col] = wid
        self.path_to_wid[wid.src] = wid
        self.sorted_widgets.append(wid)


    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        wid: Thumb | ThumbFolder 

        if a0.modifiers() & Qt.KeyboardModifier.ControlModifier and a0.key() == Qt.Key.Key_Up:
            JsonData.root = os.path.dirname(JsonData.root)
            self.level_up.emit()

        if a0.modifiers() & Qt.KeyboardModifier.ControlModifier and a0.key() == Qt.Key.Key_Down:
            wid = self.cell_to_wid.get(self.curr_cell)
            wid.view()

        elif a0.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            wid = self.cell_to_wid.get(self.curr_cell)
            if wid:
                wid.view()

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
