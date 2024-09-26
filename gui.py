import json
import os
import sys
from functools import partial
from typing import List

from PyQt5.QtCore import QEvent, QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QKeyEvent, QMouseEvent
from PyQt5.QtWidgets import (QApplication, QFileSystemModel, QFrame,
                             QGridLayout, QHBoxLayout, QLabel, QPushButton,
                             QScrollArea, QSizePolicy, QSpacerItem, QSplitter,
                             QTabBar, QTreeView, QVBoxLayout, QWidget)

from get_items import GetDirItems
from load_images import LoadImagesThread
from utils import Utils


class Storage:
    load_images_threads: list = []
    json_file = os.path.join(os.path.expanduser('~'), 'Desktop', 'last_place.json')
    json_data: dict = {}
    load_images_thread: LoadImagesThread = None


class ClickableFrame(QFrame):
    double_click = pyqtSignal()

    def mouseDoubleClickEvent(self, a0: QMouseEvent | None) -> None:
        self.double_click.emit()
        return super().mouseDoubleClickEvent(a0)


class NameLabel(QLabel):
    def __init__(self, filename: str):
        super().__init__()

        max_row = 27
        name, ext = os.path.splitext(filename)

        if len(name) >= max_row:
            cut_name = name[:max_row]
            cut_name = cut_name[:-6]
            name = cut_name + "..." + name[-3:]

        if ext:
            self.setText(f"{name}{ext}")
        else:
            self.setText(name)


class TabsWidget(QFrame):
    btn_press = pyqtSignal()
    btn_up_press = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFixedHeight(40)
        self.init_ui()

    def init_ui(self):
        layout = QGridLayout()
        layout.setContentsMargins(10, 0, 0, 0)
        self.setLayout(layout)

        self.up_button = QPushButton(text="↑", parent=self)
        self.up_button.setFixedWidth(60)
        self.up_button.clicked.connect(self.btn_up_press.emit)
        layout.addWidget(self.up_button, 0, 0)

        l_spacer = QSpacerItem(1, 1, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout.addItem(l_spacer, 0, 0)

        self.tabs = QTabBar(parent=self)
        self.tabs.addTab("Имя")
        self.tabs.addTab("Размер")
        self.tabs.addTab("Дата изменения")
        self.tabs.addTab("Тип")
        self.tabs.currentChanged.connect(self.on_tab_change)

        self.tabs_data = {
                "name": {"btn_text": "Имя", "index": 0},
                "size": {"btn_text": "Размер", "index": 1},
                "modify": {"btn_text": "Дата изменения", "index": 2},
                "type": {"btn_text": "Тип", "index": 3},
                }
    
        current_tab = self.tabs_data[Storage.json_data["sort"]]
        self.tabs.setCurrentIndex(current_tab["index"])
        layout.addWidget(self.tabs, 0, 1)

        self.photo_tabs = QTabBar(parent=self)
        self.photo_tabs.addTab("Только фото")
        self.photo_tabs.addTab("Все файлы")

        if Storage.json_data["only_photo"]:
            self.photo_tabs.setCurrentIndex(0)
        else:
            self.photo_tabs.setCurrentIndex(1)
    
        self.photo_tabs.currentChanged.connect(self.on_photo_toogle)

        layout.addWidget(self.photo_tabs, 0, 2)

        sort_t = "По убыванию" if Storage.json_data["reversed"] else "По возрастанию"
        self.sort_button = QPushButton(text=sort_t, parent=self)
        self.sort_button.setFixedWidth(130)
        self.sort_button.clicked.connect(self.on_sort_toggle)
        layout.addWidget(self.sort_button, 0, 3)

        r_spacer = QSpacerItem(1, 1, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout.addItem(r_spacer, 0, 5)

    def on_photo_toogle(self):
        if Storage.json_data["only_photo"]:
            self.photo_tabs.setCurrentIndex(1)
            Storage.json_data["only_photo"] = False

        else:
            self.photo_tabs.setCurrentIndex(0)
            Storage.json_data["only_photo"] = True

        self.btn_press.emit()

    def on_tab_change(self, index):
        tab_name = self.tabs.tabText(index)

        for json_sort, tab_data in self.tabs_data.items():

            if tab_data["btn_text"] == tab_name:

                Storage.json_data["sort"] = json_sort
                self.btn_press.emit()
                self.tabs.setCurrentIndex(index)
                break

    def on_sort_toggle(self):
        if Storage.json_data["reversed"]:
            Storage.json_data["reversed"] = False
            self.sort_button.setText("По возрастанию")
        else:
            Storage.json_data["reversed"] = True
            self.sort_button.setText("По убыванию")
        self.btn_press.emit()


class SimpleFileExplorer(QWidget):
    def __init__(self):
        super().__init__()
        self.thumb_size = 210
        self.finder_items = []
        self.finder_images: dict = {}
        self.first_load = True
        ww, hh = Storage.json_data["ww"], Storage.json_data["hh"]
        self.resize(ww, hh)
        self.clmn_count = 1

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(0, 0, 0, 0)
        v_lay.setSpacing(0)
        self.setLayout(v_lay)

        tabs = TabsWidget()
        tabs.btn_press.connect(self.tab_bar_click)
        tabs.btn_up_press.connect(self.btn_up_cmd)
        v_lay.addWidget(tabs)

        splitter_wid = QWidget()
        v_lay.addWidget(splitter_wid)
        splitter_lay = QHBoxLayout()
        splitter_lay.setContentsMargins(10, 0, 10, 10)
        splitter_wid.setLayout(splitter_lay)

        self.splitter = QSplitter(Qt.Horizontal)

        self.model = QFileSystemModel()
        self.model.setRootPath("/Volumes")

        self.tree_widget = QTreeView()

        self.tree_widget.setModel(self.model)
        self.tree_widget.setRootIndex(self.model.index("/Volumes"))

        self.tree_widget.setHeaderHidden(True)
        for i in range(1, self.model.columnCount()):
            self.tree_widget.setColumnHidden(i, True)

        self.tree_widget.clicked.connect(self.on_tree_clicked)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(10)

        self.scroll_area.setWidget(self.grid_container)

        self.splitter.addWidget(self.tree_widget)
        self.splitter.addWidget(self.scroll_area)

        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)

        splitter_lay.addWidget(self.splitter)

        self.resize_timer = QTimer(parent=self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.setInterval(500)
        self.resize_timer.timeout.connect(self.reload_grid_layout)

        self.splitter.splitterMoved.connect(self.custom_resize_event)
        self.resizeEvent = self.custom_resize_event

        self.load_last_place()
        self.set_path_title()

    def btn_up_cmd(self):
        path = self.get_current_path()
        path = os.path.dirname(path)
        index = self.model.index(path)
        self.tree_widget.setCurrentIndex(index)
        self.tree_widget.expand(index)
        Storage.json_data["last_place"] = path

        self.set_path_title()
        self.get_finder_items(path)
        self.reload_grid_layout()

    def tab_cmd(self, sort: str):
        Storage.json_data["sort"] = sort
        self.reload_grid_layout()

    def reload_grid_layout(self, event=None):
        container_width = self.splitter.width() - self.tree_widget.width() - 20
        clmn_count = container_width // self.thumb_size

        if clmn_count < 1:
            clmn_count = 1

        self.clmn_count = clmn_count
        Utils.clear_layout(layout=self.grid_layout)
        self.finder_images.clear()

        row, col = 0, 0
        finder_items_sort = []

        for src in self.finder_items:

            src: str

            try:
                if os.path.isfile(src):
                    file_name = os.path.basename(src)
                    stats = os.stat(src)
                    file_size = stats.st_size
                    modification_time = stats.st_mtime
                    file_type = os.path.splitext(file_name)[1]

                else:
                    file_name = src.split(os.sep)[-1]
                    stats = os.stat(src)
                    file_size = stats.st_size
                    modification_time = stats.st_mtime
                    file_type = "folder"

                file_info = (src, file_name, file_size, modification_time, file_type)
                finder_items_sort.append(file_info)

            except (FileNotFoundError, TypeError) as e:
                print(e, src)
                continue

        if Storage.json_data["sort"] == "name":
            finder_items_sort = sorted(finder_items_sort, key=lambda x: x[1])

        elif Storage.json_data["sort"] == "size":
            finder_items_sort = sorted(finder_items_sort, key=lambda x: x[2])

        elif Storage.json_data["sort"] == "modify":
            finder_items_sort = sorted(finder_items_sort, key=lambda x: x[3])

        elif Storage.json_data["sort"] == "type":
            finder_items_sort = sorted(finder_items_sort, key=lambda x: x[4])

        if Storage.json_data["reversed"]:
            finder_items_sort = reversed(finder_items_sort)

        for src, filename, size, modified, filetype in finder_items_sort:
            wid = QFrame()
            wid.setFrameShape(QFrame.Shape.StyledPanel)
            wid.mouseDoubleClickEvent = partial(self.on_wid_double_clicked, src)

            v_lay = QVBoxLayout()
            wid.setLayout(v_lay)

            img_label = QLabel()
            img_label.setFixedSize(self.thumb_size, self.thumb_size)
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v_lay.addWidget(img_label)

            filename = os.path.basename(src)
            img_name = NameLabel(filename)
            v_lay.addWidget(img_name)

            self.grid_layout.addWidget(wid, row, col)

            col += 1
            if col >= clmn_count:
                col = 0
                row += 1

            try:
                self.finder_images[(src, size, modified)] = img_label
            except FileNotFoundError as e:
                print(e, src)

        row_spacer = QSpacerItem(1, 1, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.grid_layout.addItem(row_spacer, row + 1, 0)
        clmn_spacer = QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.grid_layout.addItem(clmn_spacer, 0, clmn_count + 1)

        self.load_images()

    def load_images(self):
        for i in Storage.load_images_threads:
            i: LoadImagesThread
            i.stop_thread.emit()

            if i.isFinished():
                Storage.load_images_threads.remove(i)



        new_thread = LoadImagesThread(self.finder_images, self.thumb_size)
        Storage.load_images_threads.append(new_thread)
        new_thread.start()

    def set_path_title(self):
        path = self.get_current_path()
        self.setWindowTitle(os.path.basename(path))

    def on_tree_clicked(self, index):
        path = self.model.filePath(index)

        if os.path.isdir(path):
            self.tree_widget.setCurrentIndex(index)
            self.get_finder_items(path)
            self.reload_grid_layout()
            self.set_path_title()
            Storage.json_data["last_place"] = path

    def on_wid_double_clicked(self, path, event):
        
        if os.path.isdir(path):

            index = self.model.index(path)
            self.tree_widget.setCurrentIndex(index)
            self.tree_widget.expand(index)
            self.set_path_title()
            self.get_finder_items(path)
            self.reload_grid_layout()

            Storage.json_data["last_place"] = path

    def get_current_path(self):
        index = self.tree_widget.currentIndex()
        return self.model.filePath(index)

    def tab_bar_click(self):
        self.get_finder_items(self.get_current_path())
        self.reload_grid_layout()

    def get_finder_items(self, path):
        self.finder_items.clear()

        if os.path.isdir(path):

            try:

                if Storage.json_data["only_photo"]:
                    self.finder_items = []

                    for item in os.listdir(path):
                        item: str = os.path.join(path, item)

                        if os.path.isdir(item):
                            self.finder_items.append(item)
                        
                        elif item.lower().endswith((".jpg", "jpeg", ".tif", ".tiff", ".psd", ".psb", ".png")):
                            self.finder_items.append(item)

                else:
                    self.finder_items = [
                        os.path.join(path, item)
                        for item in os.listdir(path)
                        ]
                    
            except PermissionError as e:
                pass

    def load_last_place(self):
        last_place = Storage.json_data["last_place"]

        if last_place and os.path.exists(last_place):
            index = self.model.index(last_place)
            self.tree_widget.setCurrentIndex(index)
            self.tree_widget.expand(index)

            self.get_finder_items(last_place)
            self.reload_grid_layout()

    def custom_resize_event(self, event=None):
        Storage.json_data["ww"] = self.geometry().width()
        Storage.json_data["hh"] = self.geometry().height()
        self.resize_timer.stop()
        self.resize_timer.start()

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self.hide()
        a0.ignore()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_W:
            if a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.hide()

        elif a0.key() == Qt.Key.Key_Q:
            if a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
                QApplication.instance().quit()


class CustomApp(QApplication):
    def __init__(self, argv: List[str]) -> None:
        super().__init__(argv)
        self.load_json_data()
        self.aboutToQuit.connect(self.on_exit)
        self.installEventFilter(self)
        QTimer.singleShot(1200, self.on_load)

    def on_load(self):
        self.topLevelWidgets()[0].setFocus()

    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if a1.type() == QEvent.Type.ApplicationActivate:
            self.topLevelWidgets()[0].show()
        return super().eventFilter(a0, a1)

    def on_exit(self):
        with open(Storage.json_file, 'w') as f:
            json.dump(Storage.json_data, f, indent=4, ensure_ascii=False)

    def load_json_data(self) -> dict:
        if os.path.exists(Storage.json_file):
            with open(Storage.json_file, 'r') as f:
                Storage.json_data = json.load(f)
        else:
            with open(Storage.json_file, 'w') as f:
                Storage.json_data = {
                    "last_place": "",
                    "ww": 1050,
                    "hh": 700,
                    "sort": "name",
                    "reversed": False,
                    "only_photo": False
                    }
                json.dump(Storage.json_data, f, indent=4)