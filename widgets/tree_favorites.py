import subprocess

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QDropEvent, QKeyEvent, QMouseEvent
from PyQt5.QtWidgets import (QAction, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMenu)

from cfg import Config
from utils import Utils


class FavItem(QLabel):
    on_fav_click = pyqtSignal()
    del_click = pyqtSignal()
    rename_finished = pyqtSignal(str)

    def __init__(self, name: str, src: str):
        super().__init__(text=name)
        self.name = name
        self.src = src

        self.setFixedHeight(25)

        # Добавляем QLineEdit для редактирования имени
        self.name_editor = QLineEdit(self)
        self.name_editor.setText(name)
        self.name_editor.setVisible(False)
        self.name_editor.setStyleSheet("padding-left: 2px; padding-right: 20px;")
        self.name_editor.setFixedSize(170, 25)

        self.context_menu = QMenu(self)

        view_ac = QAction("Просмотр", self)
        view_ac.triggered.connect(lambda: self.on_fav_click.emit())
        self.context_menu.addAction(view_ac)

        open_finder_action = QAction("Показать в Finder", self)
        open_finder_action.triggered.connect(lambda: self.open_in_finder(src))
        self.context_menu.addAction(open_finder_action)

        self.context_menu.addSeparator()

        copy_path_action = QAction("Скопировать путь до папки", self)
        copy_path_action.triggered.connect(lambda: Utils.copy_path(src))
        self.context_menu.addAction(copy_path_action)

        self.context_menu.addSeparator()

        fav_action = QAction("Удалить из избранного", self)
        fav_action.triggered.connect(lambda: self.del_click.emit())
        self.context_menu.addAction(fav_action)

        rename_action = QAction("Переименовать", self)
        rename_action.triggered.connect(self.rename_cmd)
        self.context_menu.addAction(rename_action)

        self.setContentsMargins(10, 0, 10, 0)

    def open_in_finder(self, path: str):
        subprocess.call(["open", "-R", path])

    def rename_cmd(self):
        self.setText("")
        self.name_editor.setVisible(True)
        self.name_editor.setFocus()
        self.name_editor.selectAll()

    def finish_rename(self):
        new_name = self.name_editor.text().strip()
        if new_name:
            self.name = new_name
            self.setText(new_name)
            self.rename_finished.emit(new_name)
        self.name_editor.setVisible(False)
        self.setText(self.name)

    def cancel_rename(self):
        self.name_editor.setVisible(False)
        self.setText(self.name)
        self.rename_finished.emit(self.name)

    def keyPressEvent(self, ev: QKeyEvent | None) -> None:
        if ev.key() == Qt.Key.Key_Return:
            self.finish_rename()
        elif ev.key() == Qt.Key.Key_Escape:
            self.cancel_rename()

        return super().keyPressEvent(ev)

    def mouseReleaseEvent(self, ev: QMouseEvent | None) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self.on_fav_click.emit()

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:
        self.context_menu.exec_(ev.globalPos())


class TreeFavorites(QListWidget):
    on_fav_clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.init_ui()

    def init_ui(self):
        favs: dict = Config.json_data["favs"]
        for src, name in favs.items():
            self.add_item(name, src)

    def add_item(self, name: str, src: str):
        item = FavItem(name, src)
        item.del_click.connect(lambda: self.del_item(src))
        item.on_fav_click.connect(lambda: self.on_fav_clicked.emit(src))
        item.rename_finished.connect(lambda new_name: self.update_name(src, new_name))

        list_item = QListWidgetItem()
        list_item.setSizeHint(item.sizeHint())

        self.addItem(list_item)
        self.setItemWidget(list_item, item)

    def update_name(self, src: str, new_name: str):
        # Обновляем имя в данных Config.json_data
        favs: dict = Config.json_data.get("favs")
        if src in favs:
            favs[src] = new_name

    def del_item(self, src: str):
        favs: dict = Config.json_data.get("favs")
        favs.pop(src)
        self.clear()
        self.init_ui()
    
    def dropEvent(self, event: QDropEvent | None) -> None:
        super().dropEvent(event)
        new_order = {}
        for i in range(self.count()):
            item = self.item(i)
            fav_widget = self.itemWidget(item)
            if isinstance(fav_widget, FavItem):
                new_order[fav_widget.src] = fav_widget.name

        Config.json_data["favs"] = new_order