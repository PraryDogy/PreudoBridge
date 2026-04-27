import os

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QDropEvent, QIcon
from PyQt5.QtWidgets import QListWidget, QListWidgetItem

from cfg import JsonData, Static
from system.items import (ContextItem, FavItem, MainWinItem, RemoveItem,
                          RenameItem)

from ._base_widgets import UMenu
from .actions import CommonActions, FavActions, ThumbActions


class ListItemBase(QListWidgetItem):
    hh = 30

    def __init__(self, name: str, src: str, main_win_item: MainWinItem, parent: QListWidget):
        super().__init__()
        self.setSizeHint(QSize(parent.width(), self.hh))
        self.setText(name)

        self.main_win_item = main_win_item
        self.name = name
        self.src = src


class ListItem(ListItemBase):
    def __init__(self, name, src, main_win_item, parent):
        super().__init__(name, src, main_win_item, parent)


class ListItemPin(ListItemBase):
    def __init__(self, name, src, main_win_item, parent):
        super().__init__(name, src, main_win_item, parent)
        self.setFlags(self.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)


class ListItemSpacer(QListWidgetItem):
    hh = 10
    def __init__(self, parent: QListWidget):
        super().__init__()
        self.setSizeHint(QSize(parent.width(), self.hh))
        self.setFlags(Qt.ItemFlag.NoItemFlags)


class MenuFavs(QListWidget):
    new_history_item = pyqtSignal(str)
    load_st_grid = pyqtSignal(str)
    new_main_win = pyqtSignal(str)
    reveal = pyqtSignal(list)
    copy_urls = pyqtSignal(list)
    copy_names = pyqtSignal(list)
    rename_fav = pyqtSignal(FavItem)
    remove_fav = pyqtSignal(FavItem)
    folder_icon: QIcon
    folder_pin_icon: QIcon

    def __init__(self, main_win_item: MainWinItem):
        super().__init__()
        self.main_win_item = main_win_item
        self.url_to_item: dict[str, ListItemBase] = {}

        self.horizontalScrollBar().setDisabled(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setAcceptDrops(True)
        self.create_icons()
        self.init_ui()

    def create_icons(self):
        folder = os.path.join(Static.internal_images_dir, "folder.png")
        folder_pin = os.path.join(Static.internal_images_dir, "folder_pin.png")
        self.folder_icon = QIcon(folder)
        self.folder_pin_icon = QIcon(folder_pin)

    def init_ui(self):
        self.clear()
        self.url_to_item.clear()

        user = os.path.expanduser("~")
        icloud = "Library/Mobile Documents/com~apple~CloudDocs"
        fav_pin = {
            "/Volumes": "Компьютер",
            os.path.join(user, icloud): "iCloud Drive",
            os.path.join(user, "Desktop"): "Рабочий стол",
            os.path.join(user, "Downloads"): "Загрузки"
        }

        for src, name in fav_pin.items():
            list_item = ListItemPin(name, src, self.main_win_item, self)
            list_item.setIcon(self.folder_pin_icon)
            self.addItem(list_item)
            self.url_to_item[src] = list_item

            if self.main_win_item.abs_current_dir == src:
                self.setCurrentItem(list_item)

        item = ListItemSpacer(self)
        self.addItem(item)

        for src, name in JsonData.favs.items():
            list_item = ListItem(name, src, self.main_win_item, self)
            list_item.setIcon(self.folder_icon)
            self.addItem(list_item)
            self.url_to_item[src] = list_item

            if self.main_win_item.abs_current_dir == src:
                self.setCurrentItem(list_item)

    def select_fav(self, src: str):
        self.clearSelection()
        if src in self.url_to_item:
            self.setCurrentItem(self.url_to_item[src])
    
    def add_fav_cmd(self, path: str, text: str):
        JsonData.favs[path] = text
        JsonData.write_json_data()
        list_item = ListItem(text, path, self.main_win_item, self)
        list_item.setIcon(self.folder_icon)
        self.addItem(list_item)
        self.url_to_item[path] = list_item

    def rename_fav_finalize(self, fav_item: FavItem):
        item = self.url_to_item[fav_item.path]
        JsonData.favs[fav_item.path] = fav_item.text
        JsonData.write_json_data()
        item.setText(fav_item.text)
        item.name = fav_item.text

    def remove_fav_cmd(self, fav_item: ListItemBase):

        def finished():
            JsonData.favs.pop(fav_item.src)
            JsonData.write_json_data()
            self.takeItem(self.row(fav_item))

        item = RemoveItem(
            urls=[fav_item.src, ],
            callback=lambda: finished()
        )
        self.remove_fav.emit(item)

    def open_fav_cmd(self, path: str):
        self.new_history_item.emit(path)
        self.load_st_grid.emit(path)
    
    def contextMenuEvent(self, a0):
        list_item: ListItemBase = self.itemAt(a0.pos())
        if not list_item:
            return

        urls = [list_item.src, ]
        context_item = ContextItem(
            main_win_item=self.main_win_item,
            urls=urls,
            data_items=list()
        )
        fav_item = FavItem(
            text=list_item.name,
            path=list_item.src
        )
        menu = UMenu(parent=self)
        thumb_actions = ThumbActions(menu, context_item)
        fav_action = FavActions(menu, context_item)
        common_actions = CommonActions(menu, context_item)

        menu.add_action(
            action=thumb_actions.open_thumb,
            cmd=lambda: self.open_fav_cmd(urls[0])
        )
        menu.add_action(
            action=thumb_actions.new_main_win,
            cmd=lambda: self.new_main_win.emit(urls[0])
        )
        menu.addSeparator()
        menu.add_action(
            common_actions.reveal,
            cmd=lambda: self.reveal.emit(urls)
        )
        menu.add_action(
            common_actions.copy_path,
            cmd=lambda: self.copy_urls.emit(urls)
        )
        menu.add_action(
            common_actions.copy_name,
            cmd=lambda: self.copy_names.emit(urls)
        )
        if isinstance(list_item, ListItem):
            menu.addSeparator()
            menu.add_action(
                action=thumb_actions.rename,
                cmd=lambda: self.rename_fav.emit(fav_item)
            )
            menu.add_action(
                action=fav_action.fav_remove,
                cmd=lambda: self.remove_fav_cmd(fav_item)
            )
        menu.show_under_cursor()
        return super().contextMenuEvent(a0)
    
    def mouseReleaseEvent(self, e):
        item: ListItemBase = self.itemAt(e.pos())
        if isinstance(item, ListItemSpacer):
            return
        if item:
            if e.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.new_main_win.emit(item.src)
            else:
                self.open_fav_cmd(item.src)
        else:
            self.clearSelection()
        return super().mouseReleaseEvent(e)

    def dragMoveEvent(self, e):
        index = self.indexAt(e.pos()).row()
        if 0 < index < 5:
            e.ignore()
        else:
            super().dragMoveEvent(e)

    def dragEnterEvent(self, e):
        e.acceptProposedAction()
    
    def dropEvent(self, a0: QDropEvent | None) -> None:        
        urls = a0.mimeData().urls()
        if not urls:
            super().dropEvent(a0)
            new_order = {}
            for i in range(self.count()):
                fav_item = self.item(i)
                if isinstance(fav_item, ListItem):
                    new_order[fav_item.src] = fav_item.name
                else:
                    continue
            if new_order:
                JsonData.favs = new_order
                JsonData.write_json_data()
        else:
            url_ = urls[-1].toLocalFile()
            url_ = url_.rstrip(os.sep)
            if os.path.isdir(url_) and url_ not in JsonData.favs:
                print(123)
                item = RenameItem(
                    text=os.path.basename(url_),
                    callback=lambda text: self.add_fav_cmd(url_, text)
                )
                self.rename_fav.emit(item)
