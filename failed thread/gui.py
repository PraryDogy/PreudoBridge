import json
import os
import subprocess
import sys
from functools import partial
from typing import List

from PyQt5.QtCore import QDir, QEvent, QObject, QPoint, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QKeyEvent, QMouseEvent
from PyQt5.QtWidgets import (QAction, QApplication, QFileSystemModel, QFrame,
                             QGridLayout, QHBoxLayout, QLabel, QMenu,
                             QMessageBox, QPushButton, QScrollArea,
                             QSizePolicy, QSpacerItem, QSplitter, QTabBar,
                             QTreeView, QVBoxLayout, QWidget)

from cfg import Config
from database import Dbase
from load_images import ImagesGridThread
from utils import Utils


class Storage:
    threads: list = []


class TabsWidget(QFrame):
    btn_press = pyqtSignal()
    btn_up_press = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFixedHeight(40)
        self.init_ui()

    def init_ui(self):
        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        l_spacer = QSpacerItem(1, 1, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout.addItem(l_spacer, 0, 0)

        self.up_button = QPushButton(text="↑", parent=self)
        self.up_button.setFixedWidth(60)
        self.up_button.clicked.connect(self.btn_up_press.emit)
        layout.addWidget(self.up_button, 0, 1)

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
    
        current_tab = self.tabs_data[Config.json_data["sort"]]
        self.tabs.setCurrentIndex(current_tab["index"])
        layout.addWidget(self.tabs, 0, 2)

        self.photo_tabs = QTabBar(parent=self)
        self.photo_tabs.addTab("Только фото")
        self.photo_tabs.addTab("Все файлы")

        if Config.json_data["only_photo"]:
            self.photo_tabs.setCurrentIndex(0)
        else:
            self.photo_tabs.setCurrentIndex(1)
    
        self.photo_tabs.currentChanged.connect(self.on_photo_toogle)

        layout.addWidget(self.photo_tabs, 0, 3)

        sort_t = "По убыванию" if Config.json_data["reversed"] else "По возрастанию"
        self.sort_button = QPushButton(text=sort_t, parent=self)
        self.sort_button.setFixedWidth(130)
        self.sort_button.clicked.connect(self.on_sort_toggle)
        layout.addWidget(self.sort_button, 0, 4)

        r_spacer = QSpacerItem(1, 1, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout.addItem(r_spacer, 0, 5)

    def on_photo_toogle(self):
        if Config.json_data["only_photo"]:
            self.photo_tabs.setCurrentIndex(1)
            Config.json_data["only_photo"] = False

        else:
            self.photo_tabs.setCurrentIndex(0)
            Config.json_data["only_photo"] = True

        self.btn_press.emit()

    def on_tab_change(self, index):
        tab_name = self.tabs.tabText(index)

        for json_sort, tab_data in self.tabs_data.items():

            if tab_data["btn_text"] == tab_name:

                Config.json_data["sort"] = json_sort
                self.btn_press.emit()
                self.tabs.setCurrentIndex(index)
                break

    def on_sort_toggle(self):
        if Config.json_data["reversed"]:
            Config.json_data["reversed"] = False
            self.sort_button.setText("По возрастанию")
        else:
            Config.json_data["reversed"] = True
            self.sort_button.setText("По убыванию")
        self.btn_press.emit()


class SimpleFileExplorer(QWidget):
    def __init__(self):
        super().__init__()
        self.finder_items = []
        self.finder_images: dict = {}
        self.first_load = True
        ww, hh = Config.json_data["ww"], Config.json_data["hh"]
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
        splitter_wid.setLayout(splitter_lay)

        self.splitter = QSplitter(Qt.Horizontal)

        left_wid = QWidget()
        left_lay = QVBoxLayout()
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_wid.setLayout(left_lay)
        self.splitter.addWidget(left_wid)
        
        self.model = QFileSystemModel()
        self.model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot)
        if Config.json_data["hidden_dirs"]:
            self.model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot | QDir.Hidden)
        self.model.setRootPath("/Volumes")

        self.tree_widget = QTreeView()

        self.tree_widget.setModel(self.model)
        self.tree_widget.setRootIndex(self.model.index("/Volumes"))

        self.tree_widget.setHeaderHidden(True)
        for i in range(1, self.model.columnCount()):
            self.tree_widget.setColumnHidden(i, True)

        self.tree_widget.clicked.connect(self.on_tree_clicked)

        left_lay.addWidget(self.tree_widget)

        self.storage_btn = QPushButton()
        left_lay.addWidget(self.storage_btn)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(5)

        self.scroll_area.setWidget(self.grid_container)

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
        Config.json_data["root"] = path

        self.set_path_title()
        self.reload_grid_layout()

    def tab_cmd(self, sort: str):
        Config.json_data["sort"] = sort
        self.reload_grid_layout()

    def reload_grid_layout(self, event=None):
        container_width = self.splitter.width() - self.tree_widget.width() - 20
        clmn_count = container_width // Config.thumb_size

        if clmn_count < 1:
            clmn_count = 1

        self.clmn_count = clmn_count
        Utils.clear_layout(layout=self.grid_layout)
        self.finder_images.clear()

        ...

        self.storage_btn.setText(f"Занято: {Dbase.get_file_size()}")

        for i in Storage.threads:
            i: ImagesGridThread
            i.stop_thread.emit()

            if i.isFinished():
                Storage.threads.remove(i)

        new_thread = ImagesGridThread(self.grid_layout, self.get_current_path(), clmn_count)
        Storage.threads.append(new_thread)
        new_thread.start()

    def set_path_title(self):
        path = self.get_current_path()
        self.setWindowTitle(os.path.basename(path))

    def on_tree_clicked(self, index):
        path = self.model.filePath(index)

        if os.path.isdir(path):
            self.tree_widget.setCurrentIndex(index)
            self.reload_grid_layout()
            self.set_path_title()
            Config.json_data["root"] = path

    def on_wid_double_clicked(self, path):
        
        if os.path.isdir(path):

            index = self.model.index(path)
            self.tree_widget.setCurrentIndex(index)
            self.tree_widget.expand(index)
            self.set_path_title()
            self.reload_grid_layout()

            Config.json_data["root"] = path

    def get_current_path(self):
        index = self.tree_widget.currentIndex()
        return self.model.filePath(index)

    def tab_bar_click(self):
        self.reload_grid_layout()

    def load_last_place(self):
        last_place = Config.json_data["root"]

        if last_place and os.path.exists(last_place):
            index = self.model.index(last_place)
            self.tree_widget.setCurrentIndex(index)
            self.tree_widget.expand(index)
            self.reload_grid_layout()

    def custom_resize_event(self, event=None):
        Config.json_data["ww"] = self.geometry().width()
        Config.json_data["hh"] = self.geometry().height()
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

        elif a0.key() == Qt.Key.Key_Up:
            if a0.nativeModifiers() == 11534600:
                self.btn_up_cmd()


class CustomApp(QApplication):
    def __init__(self, argv: List[str]) -> None:
        super().__init__(argv)
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
        for thread in Storage.threads:
            thread: ImagesGridThread
            thread.stop_thread.emit()
            thread.wait()

        with open(Config.json_file, 'w') as f:
            json.dump(Config.json_data, f, indent=4, ensure_ascii=False)
