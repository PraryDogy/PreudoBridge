import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QDropEvent, QMouseEvent
from PyQt5.QtWidgets import QAction, QLabel, QListWidget, QListWidgetItem

from cfg import JsonData
from utils import Utils

from ._base_widgets import UMenu
from .actions import CopyPath, FavRemove, OpenInWindow, RevealInFinder, View
from .rename_win import RenameWin

RENAME_T = "Переименовать"


class FavItem(QLabel):
    remove_fav_item = pyqtSignal()
    renamed = pyqtSignal(str)
    path_changed = pyqtSignal()
    new_history_item = pyqtSignal(str)
    load_st_grid_sig = pyqtSignal(tuple)
    open_in_new_win = pyqtSignal(str)

    def __init__(self, name: str, src: str):
        super().__init__(text=name)

        self.name = name
        self.src = src
        self.setFixedHeight(25)
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
        self.load_st_grid_sig.emit((self.src, None))

    def mouseReleaseEvent(self, ev: QMouseEvent | None) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            if not os.path.exists(self.src):
                fixed_path = Utils.fix_path_prefix(self.src)
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
                    self.path_changed.emit()

            self.view_fav()

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:
        menu_ = UMenu(self)

        view_ac = View(menu_)
        view_ac.triggered.connect(self.view_fav)
        menu_.addAction(view_ac)

        open_new_win = OpenInWindow(menu_)
        open_new_win.triggered.connect(lambda: self.open_in_new_win.emit(self.src))
        menu_.addAction(open_new_win)

        open_finder_action = RevealInFinder(menu_, self.src)
        menu_.addAction(open_finder_action)

        menu_.addSeparator()

        copy_path_action = CopyPath(menu_, self.src)
        menu_.addAction(copy_path_action)

        menu_.addSeparator()

        rename_action = QAction(RENAME_T, menu_)
        rename_action.triggered.connect(self.rename_cmd)
        menu_.addAction(rename_action)

        cmd_ = lambda: self.remove_fav_item.emit()
        fav_action = FavRemove(menu_)
        fav_action.triggered.connect(cmd_)
        menu_.addAction(fav_action)

        menu_.exec_(ev.globalPos())


class FavsMenu(QListWidget):
    LIST_ITEM = "list_item"
    FAV_ITEM = "fav_item"
    new_history_item = pyqtSignal(str)
    load_st_grid_sig = pyqtSignal(tuple)
    set_main_dir_sig = pyqtSignal()
    open_in_new_win = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.main_dir: str = None
        self.horizontalScrollBar().setDisabled(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.wids: dict[str, QListWidgetItem] = {}
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setAcceptDrops(True)
        self.set_main_dir_sig.emit()
        self.init_ui()

    def set_main_dir(self, main_dir: str):
        self.main_dir = main_dir

    def init_ui(self):
        self.clear()
        self.wids.clear()

        for src, name in JsonData.favs.items():
            result = self.add_fav_widget_item(name, src)
            item: QListWidgetItem = result[self.LIST_ITEM]
            self.wids[src] = item

            if self.main_dir == src:
                self.setCurrentItem(item)

    def select_fav(self, src: str):
        wid = self.wids.get(src)
        if wid:
            self.setCurrentItem(wid)
        else:
            self.clearSelection()

    def fav_cmd(self, data: tuple):
        """
        args: ("select"/"add"/"del", path)
        """
        cmd, src = data

        if cmd == "select":
            self.select_fav(src)
        elif cmd == "add":
            self.add_to_favs_main(src)
        elif cmd == "del":
            self.del_item(src)
        else:
            raise Exception("tree favorites wrong flag", cmd.get("cmd"))

    def add_to_favs_main(self, src: str):

        if src not in JsonData.favs:
            cmd_ = lambda name: self.add_to_favs_main_fin(src=src, name=name)
            name = os.path.basename(src)
            self.win_set_name = RenameWin(text=name)
            self.win_set_name.finished_.connect(cmd_)
            self.win_set_name.center(self.window())
            self.win_set_name.show()

    def add_to_favs_main_fin(self, src: str, name: str):
            JsonData.favs[src] = name
            self.add_fav_widget_item(name, src)
            JsonData.write_config()

    def path_changed_cmd(self):
        self.set_main_dir_sig.emit()
        self.init_ui()

    def add_fav_widget_item(self, name: str, src: str) -> dict:
        fav_item = FavItem(name, src)
        fav_item.new_history_item.connect(self.new_history_item)
        fav_item.load_st_grid_sig.connect(self.load_st_grid_sig.emit)
        fav_item.remove_fav_item.connect(lambda: self.del_item(src))
        fav_item.open_in_new_win.connect(lambda dir: self.open_in_new_win.emit(dir))
        fav_item.renamed.connect(
            lambda new_name: self.update_name(src, new_name)
        )
        fav_item.path_changed.connect(self.path_changed_cmd)

        list_item = QListWidgetItem(parent=self)
        list_item.setSizeHint(fav_item.sizeHint())

        self.addItem(list_item)
        self.setItemWidget(list_item, fav_item)

        self.wids[src] = list_item

        return {self.LIST_ITEM: list_item, self.FAV_ITEM: fav_item}

    def update_name(self, src: str, new_name: str):
        if src in JsonData.favs:
            JsonData.favs[src] = new_name

    def del_item(self, src: str):
        JsonData.favs.pop(src)
        JsonData.write_config()
        self.set_main_dir_sig.emit()
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
            url_ = Utils.normalize_slash(url_)
            
            if url_ not in JsonData.favs and os.path.isdir(url_):
                self.add_to_favs_main(src=url_)
