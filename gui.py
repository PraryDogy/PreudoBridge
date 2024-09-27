import json
import os
import subprocess

from PyQt5.QtCore import QDir, QEvent, QObject, QPoint, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QKeyEvent, QPixmap
from PyQt5.QtWidgets import (QAction, QApplication, QFileSystemModel, QFrame,
                             QGridLayout, QHBoxLayout, QLabel, QMenu,
                             QMessageBox, QPushButton, QScrollArea,
                             QSizePolicy, QSpacerItem, QSplitter, QTabBar,
                             QTreeView, QVBoxLayout, QWidget, QHeaderView)

from cfg import Config
from database import Dbase
from get_finder_items import LoadFinderItems
from load_images import LoadImagesThread
from utils import Utils


class Storage:
    load_images_threads: list = []
    load_finder_threads: list = []


class NameLabel(QLabel):
    def __init__(self, filename: str):
        super().__init__()

        # max_row = 27

        # if len(filename) >= max_row:
        #     cut_name = filename[:max_row]
        #     filename = cut_name + "..."

        self.setText(self.split_text(filename))

    def split_text(self, text: str) -> list[str]:
        max_length = 27
        lines = []
        
        # Разбиваем текст на строки длиной не более 27 символов
        while len(text) > max_length:
            lines.append(text[:max_length])
            text = text[max_length:]

        # Добавляем последнюю строку (если есть остаток)
        if text:
            lines.append(text)

        # Обрезаем, если строк больше двух
        if len(lines) > 2:
            lines = lines[:2]
            lines[-1] = lines[-1][:max_length-3] + '...'  # Отсекаем и добавляем троеточие

        return "\n".join(lines)

class Thumbnail(QFrame):
    double_click = pyqtSignal(str)

    def __init__(self, filename: str, src: str):
        super().__init__()
        self.src = src

        self.setFrameShape(QFrame.Shape.StyledPanel)
        tooltip = filename + "\n" + src
        self.setToolTip(tooltip)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.mouseDoubleClickEvent = lambda e: self.double_click.emit(src)

        v_lay = QVBoxLayout()
        self.setLayout(v_lay)

        self.img_label = QLabel()
        self.img_label.setFixedSize(Config.thumb_size, Config.thumb_size)
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_lay.addWidget(self.img_label)

        filename = os.path.basename(src)
        img_name = NameLabel(filename)
        v_lay.addWidget(img_name)

    def show_context_menu(self, pos: QPoint):
        self.setFrameShape(QFrame.Shape.Panel)

        context_menu = QMenu(self)

        # Пункт "Просмотр"
        view_action = QAction("Просмотр", self)
        view_action.triggered.connect(self.view_file)
        context_menu.addAction(view_action)

        # Пункт "Открыть в программе по умолчанию"
        open_action = QAction("Открыть в программе по умолчанию", self)
        open_action.triggered.connect(self.open_default)
        context_menu.addAction(open_action)

        # Сепаратор
        context_menu.addSeparator()

        # Пункт "Показать в Finder"
        show_in_finder_action = QAction("Показать в Finder", self)
        show_in_finder_action.triggered.connect(self.show_in_finder)
        context_menu.addAction(show_in_finder_action)

        # Отображаем меню
        context_menu.exec_(self.mapToGlobal(pos))

        self.setFrameShape(QFrame.Shape.StyledPanel)

    def view_file(self):
        QMessageBox.information(self, "Просмотр", f"Просмотр файла: {self.src}")

    def open_default(self):
        subprocess.call(["open", self.src])

    def show_in_finder(self):
        subprocess.call(["open", "-R", self.src])


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
        tabs.btn_press.connect(self.get_finder_items)
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

        self.tree_widget.header().setStretchLastSection(False)
        self.tree_widget.header().setSectionResizeMode(QHeaderView.ResizeToContents)

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
        self.resize_timer.timeout.connect(self.get_finder_items)

        self.splitter.splitterMoved.connect(self.custom_resize_event)
        self.resizeEvent = self.custom_resize_event

        self.load_last_place()
        self.setWindowTitle(Config.json_data["root"])

    def btn_up_cmd(self):
        path = os.path.dirname(Config.json_data["root"])
        Config.json_data["root"] = path

        index = self.model.index(path)
        self.tree_widget.setCurrentIndex(index)
        self.tree_widget.expand(index)

        self.setWindowTitle(Config.json_data["root"])
        self.get_finder_items()

    def reload_grid_layout(self, event=None):
        container_width = self.splitter.width() - self.tree_widget.width() - 20
        clmn_count = container_width // Config.thumb_size

        if clmn_count < 1:
            clmn_count = 1

        self.clmn_count = clmn_count

        row, col = 0, 0

        for src, filename, size, modified, filetype in self.finder_items:
            thumbnail = Thumbnail(filename, src)
            thumbnail.double_click.connect(self.on_wid_double_clicked)

            if os.path.isdir(src):
                self.set_default_image(thumbnail.img_label, "images/folder_210.png")
            else:
                self.set_default_image(thumbnail.img_label, "images/file_210.png")

            self.grid_layout.addWidget(thumbnail, row, col)

            col += 1
            if col >= clmn_count:
                col = 0
                row += 1

            try:
                self.finder_images[(src, size, modified)] = thumbnail.img_label
            except FileNotFoundError as e:
                print(e, src)

        row_spacer = QSpacerItem(1, 1, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.grid_layout.addItem(row_spacer, row + 1, 0)
        clmn_spacer = QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.grid_layout.addItem(clmn_spacer, 0, clmn_count + 1)

        self.storage_btn.setText(f"Занято: {Dbase.get_file_size()}")
        if self.finder_images:
            self.load_images()

    def load_images(self):
        for i in Storage.load_images_threads:
            i: LoadImagesThread
            i.stop_thread.emit()

            if i.isFinished():
                Storage.load_images_threads.remove(i)

        new_thread = LoadImagesThread(self.finder_images, Config.thumb_size)
        Storage.load_images_threads.append(new_thread)
        new_thread.start()

    def on_tree_clicked(self, index):
        path = self.model.filePath(index)
        if os.path.isdir(path):
            Config.json_data["root"] = path
            self.tree_widget.setCurrentIndex(index)
            self.setWindowTitle(Config.json_data["root"])
            self.get_finder_items()

    def on_wid_double_clicked(self, path):
        if os.path.isdir(path):
            Config.json_data["root"] = path
            index = self.model.index(path)
            self.tree_widget.setCurrentIndex(index)
            self.tree_widget.expand(index)
            self.setWindowTitle(Config.json_data["root"])
            self.get_finder_items()

    def get_finder_items(self):
        self.setDisabled(True)

        Utils.clear_layout(layout=self.grid_layout)
        self.finder_images.clear()

        finder_items = LoadFinderItems(Config.json_data["root"])
        self.finder_items = finder_items.run()

        self.setDisabled(False)
        self.reload_grid_layout()

    def load_last_place(self):
        last_place = Config.json_data["root"]

        if last_place and os.path.exists(last_place):
            index = self.model.index(last_place)
            self.tree_widget.setCurrentIndex(index)
            self.tree_widget.expand(index)

            self.get_finder_items()

    def set_default_image(self, widget: QLabel, png_path: str):
        pixmap = QPixmap(png_path)
        try:
            widget.setPixmap(pixmap)
        except RuntimeError:
            pass

    def custom_resize_event(self, event=None):
        Config.json_data["ww"] = self.geometry().width()
        Config.json_data["hh"] = self.geometry().height()
        self.resize_timer.stop()
        self.resize_timer.start()

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        self.hide()
        a0.ignore()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Up:
            if a0.modifiers() == Qt.KeyboardModifier.MetaModifier:
                self.btn_up_cmd()

        elif a0.key() == Qt.Key.Key_W:
            if a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.hide()

        elif a0.key() == Qt.Key.Key_Q:
            if a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
                QApplication.instance().quit()


class CustomApp(QApplication):
    def __init__(self, argv: list[str]) -> None:
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
        for thread in Storage.load_images_threads:
            thread: LoadImagesThread
            thread.stop_thread.emit()
            thread.wait()

        with open(Config.json_file, 'w') as f:
            json.dump(Config.json_data, f, indent=4, ensure_ascii=False)

    def load_json_data(self) -> dict:
        if os.path.exists(Config.json_file):
            with open(Config.json_file, 'r') as f:
                Config.json_data = json.load(f)
        else:
            with open(Config.json_file, 'w') as f:
                Config.json_data = {
                    "root": "",
                    "ww": 1050,
                    "hh": 700,
                    "sort": "name",
                    "reversed": False,
                    "only_photo": False,
                    "hidden_dirs": False,
                    }
                json.dump(Config.json_data, f, indent=4, ensure_ascii=False)