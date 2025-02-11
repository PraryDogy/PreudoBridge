import os
from typing import Literal

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import (QContextMenuEvent, QDragEnterEvent, QDropEvent,
                         QMouseEvent)
from PyQt5.QtWidgets import QApplication, QLabel, QListWidget, QListWidgetItem

from cfg import JsonData
from signals import SignalsApp
from utils import Utils

from ._actions import CopyPath, FavRemove, Rename, RevealInFinder, View
from ._base import UMenu
from .win_rename import WinRename


class FavItem(QLabel):
    remove_fav_item = pyqtSignal()
    renamed = pyqtSignal(str)
    path_changed = pyqtSignal()

    def __init__(self, name: str, src: str):
        super().__init__(text=name)

        self.name = name
        self.src = src
        self.setFixedHeight(25)
        self.setContentsMargins(10, 0, 10, 0)

    def rename_cmd(self):
        self.win = WinRename(self.name)
        self.win.finished_.connect(self.rename_finished_cmd)
        Utils.center_win(Utils.get_main_win(), self.win)
        self.win.show()

    def rename_finished_cmd(self, text: str):
        self.setText(text)
        self.renamed.emit(text)
        JsonData.write_config()

    def try_find_path(self):
        # Проверяет возможность изменения пути, если текущий путь `self.src` недоступен.
        #
        # Метод предназначен для случаев, когда путь из избранного (`self.src`) может существовать 
        # на другом сетевом диске. Для этого:
        # 1. Удаляются первые две секции из текущего пути (`/Volumes/ИМЯ_СЕТЕВОГО_ДИСКА`).
        # 2. Подставляются новые имена сетевых дисков, перечисленных в директории `/Volumes`.
        # 3. Выполняется проверка существования нового пути.
        #    Если путь найден:
        #    - Обновляется словарь избранного (`JsonData.favs`), заменяя старый путь на новый.
        #    - Сохраняются изменения в конфигурации с помощью `JsonData.write_config`.
        #    - Вызывается сигнал `self.path_changed` для уведомления о смене пути.
        #
        # Если подходящий путь не найден, никаких изменений не производится.


        if not os.path.exists(self.src):
            cut = os.path.sep.join(
                self.src.strip(os.path.sep).split(os.path.sep)[2:]
            )

            volumes = [
                entry.path
                for entry in os.scandir("/Volumes")
                if entry.is_dir()
            ]

            for volume in volumes:
                new_src = os.path.join(volume, cut)

                if os.path.exists(new_src):
                    JsonData.favs = {
                        (new_src if path == self.src else path): path_name
                        for path, path_name in JsonData.favs.items()
                    }

                    self.src = new_src
                    JsonData.write_config()
                    self.path_changed.emit()
                    break

    def mouseReleaseEvent(self, ev: QMouseEvent | None) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:

            # проверяем, если путь не существует, возможно
            # он находится на другом сетевом диске

            self.try_find_path()
            SignalsApp.instance.new_history_item.emit(self.src)

            SignalsApp.instance.load_standart_grid_cmd(
                path=self.src,
                prev_path=None
            )

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:
        menu_ = UMenu(self)

        cmd_ = lambda: SignalsApp.instance.load_standart_grid_cmd(
            path=self.src,
            prev_path=None
        )

        view_ac = View(menu_, self.src)
        view_ac._clicked.connect(cmd_)
        menu_.addAction(view_ac)

        open_finder_action = RevealInFinder(menu_, self.src)
        menu_.addAction(open_finder_action)

        menu_.addSeparator()

        copy_path_action = CopyPath(menu_, self.src)
        menu_.addAction(copy_path_action)

        menu_.addSeparator()

        rename_action = Rename(menu_, self.src)
        rename_action._clicked.connect(self.rename_cmd)
        menu_.addAction(rename_action)

        cmd_ = lambda: self.remove_fav_item.emit()
        fav_action = FavRemove(menu_, self.src)
        fav_action._clicked.connect(cmd_)
        menu_.addAction(fav_action)

        menu_.exec_(ev.globalPos())


class TreeFavorites(QListWidget):
    def __init__(self):
        super().__init__()

        self.wids: dict[str, QListWidgetItem] = {}
        SignalsApp.instance.fav_cmd.connect(self.cmd_)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setAcceptDrops(True)
        self.init_ui()

    def init_ui(self):

        self.clear()
        self.wids.clear()

        for src, name in JsonData.favs.items():
            item = self.add_fav_widget_item(name, src)
            self.wids[src] = item

            if JsonData.root == src:
                self.setCurrentItem(item)

    def select_fav(self, src: str):
        wid = self.wids.get(src)
        if wid:
            self.setCurrentItem(wid)
        else:
            self.clearSelection()

    def cmd_(self, cmd: dict[Literal["cmd"], Literal["select", "add", "del"]]):
        """
        keys:
        cmd = select or add or remove 
        src = path to directory 
        """
        if cmd.get("cmd") == "select":
            self.select_fav(cmd.get("src"))
        elif cmd.get("cmd") == "add":
            self.add_to_favs_main(cmd.get("src"))
        elif cmd.get("cmd") == "del":
            self.del_item(cmd.get("src"))
        else:
            raise Exception("tree favorites wrong flag", cmd.get("cmd"))

    def add_to_favs_main(self, src: str):

        if src not in JsonData.favs:

            name = os.path.basename(src)
            JsonData.favs[src] = name
            self.add_fav_widget_item(name, src)

            JsonData.write_config()

    def add_fav_widget_item(self, name: str, src: str) -> QListWidgetItem:
        item = FavItem(name, src)
        item.remove_fav_item.connect(
            lambda: self.del_item(src)
        )
        item.renamed.connect(
            lambda new_name: self.update_name(src, new_name)
        )
        item.path_changed.connect(
            self.init_ui
        )

        list_item = QListWidgetItem(parent=self)
        list_item.setSizeHint(item.sizeHint())

        self.addItem(list_item)
        self.setItemWidget(list_item, item)

        self.wids[src] = list_item

        return list_item

    def update_name(self, src: str, new_name: str):
        if src in JsonData.favs:
            JsonData.favs[src] = new_name

    def del_item(self, src: str):
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
            
            if url_ not in JsonData.favs:

                self.add_to_favs_main(src=url_)
