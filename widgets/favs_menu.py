import os

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QDropEvent, QIcon, QMouseEvent
from PyQt5.QtWidgets import QAction, QLabel, QListWidget, QListWidgetItem

from cfg import JsonData
from system.items import MainWinItem
from system.shared_utils import SharedUtils
from system.utils import Utils

from ._base_widgets import UMenu
from .actions import ItemActions
# в main_win
from .rename_win import RenameWin


class FavItem(QLabel):
    remove_fav_item = pyqtSignal()
    renamed = pyqtSignal(str)
    path_fixed = pyqtSignal()
    new_history_item = pyqtSignal(str)
    load_st_grid = pyqtSignal()
    open_in_new_win = pyqtSignal(str)
    rename_text = "Переименовать"
    height_ = 25

    def __init__(self, name: str, src: str, main_win_item: MainWinItem):
        super().__init__(text=name)
        self.main_win_item = main_win_item
        self.name = name
        self.src = src
        self.setFixedHeight(FavItem.height_)
        self.setContentsMargins(10, 0, 10, 0)

    def rename_cmd(self):
        self.win_rename = RenameWin(self.name)
        self.win_rename.finished_.connect(self.rename_finished_cmd)
        self.win_rename.center(self.window())
        self.win_rename.show()

    def rename_finished_cmd(self, text: str):
        self.setText(text)
        self.renamed.emit(text)
        JsonData.write_config()

    def view_fav(self):
        self.new_history_item.emit(self.src)
        self.main_win_item.main_dir = self.src
        self.load_st_grid.emit()

    def mouseReleaseEvent(self, ev: QMouseEvent | None) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            if not os.path.exists(self.src):
                slashed = self.src.rstrip(os.sep)
                fixed_path = Utils.fix_path_prefix(slashed)
                if fixed_path:
                    # удаляем из избранного старый айтем с неверной директорией
                    # добавляем новый айтем на то же место

                    fav_items = list(JsonData.favs.items())
                    index = fav_items.index((self.src, self.name))
                    new_item = (fixed_path, self.name)
                    fav_items.pop(index)
                    fav_items.insert(index, new_item)
                    JsonData.favs = dict(fav_items)

                    self.src = fixed_path
                    JsonData.write_config()
                    # подаем сигнал в родительский виджет для обновления ui
                    self.path_fixed.emit()

            self.view_fav()

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:
        urls = [self.src]
        names = [os.path.basename(i) for i in urls]
        total = 1

        menu_ = UMenu(parent=self)

        view_ac = ItemActions.OpenSingle(menu_)
        view_ac.triggered.connect(self.view_fav)
        menu_.addAction(view_ac)

        open_new_win = ItemActions.OpenInNewWindow(menu_)
        open_new_win.triggered.connect(lambda: self.open_in_new_win.emit(self.src))
        menu_.addAction(open_new_win)

        menu_.addSeparator()

        open_finder_action = ItemActions.RevealInFinder(menu_, urls)
        menu_.addAction(open_finder_action)

        copy_path_action = ItemActions.CopyPath(menu_, urls)
        menu_.addAction(copy_path_action)

        copy_name = ItemActions.CopyName(menu_, names)
        menu_.addAction(copy_name)

        menu_.addSeparator()

        rename_action = QAction(FavItem.rename_text, menu_)
        rename_action.triggered.connect(self.rename_cmd)
        menu_.addAction(rename_action)

        cmd_ = lambda: self.remove_fav_item.emit()
        fav_action = ItemActions.FavRemove(menu_)
        fav_action.triggered.connect(cmd_)
        menu_.addAction(fav_action)

        menu_.show_under_cursor()

    def mouseReleaseEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.open_in_new_win.emit(self.src)
        elif self.src != self.main_win_item.main_dir:
            self.view_fav()
        return super().mouseReleaseEvent(e)


class FavsMenu(QListWidget):
    LIST_ITEM = "list_item"
    FAV_ITEM = "fav_item"
    new_history_item = pyqtSignal(str)
    load_st_grid = pyqtSignal()
    open_in_new_win = pyqtSignal(str)
    svg_folder = "./icons/folder.svg"
    svg_size = 16

    def __init__(self, main_win_item: MainWinItem):
        super().__init__()
        self.main_win_item = main_win_item
        self.horizontalScrollBar().setDisabled(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.wids: dict[str, QListWidgetItem] = {}
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setAcceptDrops(True)
        self.init_ui()
        self.setIconSize(QSize(self.svg_size, self.svg_size))

    def init_ui(self):
        self.clear()
        self.wids.clear()

        for src, name in JsonData.favs.items():
            result = self.add_fav_item(name, src)
            item: QListWidgetItem = result[self.LIST_ITEM]
            self.wids[src] = item

            if self.main_win_item.main_dir == src:
                self.setCurrentItem(item)

    def select_fav(self, src: str):
        wid = self.wids.get(src)
        if wid:
            self.setCurrentItem(wid)
        else:
            self.clearSelection()
            # self.setCurrentItem(None)
            # self.clearFocus()

    def add_fav(self, src: str):
        if src not in JsonData.favs:
            cmd_ = lambda name: self.on_finished_rename(src, name)
            name = os.path.basename(src)
            self.win_set_name = RenameWin(name)
            self.win_set_name.finished_.connect(cmd_)
            self.win_set_name.center(self.window())
            self.win_set_name.show()

    def on_finished_rename(self, src: str, name: str):
        JsonData.favs[src] = name
        self.add_fav_item(name, src)
        JsonData.write_config()

    def add_fav_item(self, name: str, src: str) -> dict:
        fav_item = FavItem(name, src, self.main_win_item)
        fav_item.new_history_item.connect(self.new_history_item)
        fav_item.load_st_grid.connect(self.load_st_grid.emit)
        fav_item.remove_fav_item.connect(lambda: self.del_fav(src))
        fav_item.open_in_new_win.connect(lambda dir: self.open_in_new_win.emit(dir))
        fav_item.renamed.connect(lambda name: self.update_name(src, name))
        fav_item.path_fixed.connect(lambda: self.init_ui())

        list_item = QListWidgetItem(parent=self)
        list_item.setIcon(QIcon(self.svg_folder))
        list_item.setSizeHint(fav_item.sizeHint())

        self.addItem(list_item)
        self.setItemWidget(list_item, fav_item)

        self.wids[src] = list_item

        return {self.LIST_ITEM: list_item, self.FAV_ITEM: fav_item}

    def update_name(self, src: str, new_name: str):
        if src in JsonData.favs:
            JsonData.favs[src] = new_name

    def del_fav(self, src: str):
        JsonData.favs.pop(src)
        JsonData.write_config()
        self.init_ui()

    def dragEnterEvent(self, e):
        e.acceptProposedAction()
    
    def dropEvent(self, a0: QDropEvent | None) -> None:

        urls = a0.mimeData().urls()

        if not urls:
            super().dropEvent(a0)
            new_order = {}

            for i in range(self.count()):
                item = self.item(i)
                fav_widget: FavItem = self.itemWidget(item)
                if isinstance(fav_widget, FavItem):
                    new_order[fav_widget.src] = fav_widget.name

            if new_order:
                JsonData.favs = new_order

        else:
            url_ = urls[-1].toLocalFile()
            url_ = url_.rstrip(os.sep)
            
            if url_ not in JsonData.favs and os.path.isdir(url_):
                self.add_fav(src=url_)
