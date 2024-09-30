import json
import os
import subprocess

from PyQt5.QtCore import QDir, QEvent, QObject, QPoint, Qt, QTimer, pyqtSignal, QModelIndex
from PyQt5.QtGui import QCloseEvent, QKeyEvent, QPixmap
from PyQt5.QtWidgets import (QAction, QApplication, QFileSystemModel, QFrame,
                             QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                             QMenu, QMessageBox, QPushButton, QScrollArea,
                             QSizePolicy, QSpacerItem, QSplitter, QTabBar,
                             QTreeView, QVBoxLayout, QWidget, QTabWidget)

from cfg import Config
from database import Dbase
from get_finder_items import LoadFinderItems
from image_viewer import WinImageView
from load_images import LoadImagesThread
from utils import Utils


class Storage:
    load_images_threads: list = []
    load_finder_threads: list = []


class NameLabel(QLabel):
    def __init__(self, filename: str):
        super().__init__()
        self.setText(self.split_text(filename))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

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
    double_click = pyqtSignal()
    img_view_closed = pyqtSignal(str)

    def __init__(self, filename: str, src: str):
        super().__init__()
        self.setFixedSize(250, 300)
        self.src = src

        self.setFrameShape(QFrame.Shape.NoFrame)
        tooltip = filename + "\n" + src
        self.setToolTip(tooltip)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.mouseDoubleClickEvent = lambda e: self.double_click.emit()

        v_lay = QVBoxLayout()
        self.setLayout(v_lay)

        self.img_label = QLabel()
        self.img_label.setFixedHeight(Config.thumb_size)
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

        self.setFrameShape(QFrame.Shape.NoFrame)

    def view_file(self):
        if self.src.endswith(Config.img_ext):
            self.win = WinImageView(self, self.src)
            self.win.closed.connect(lambda src: self.img_view_closed.emit(src))
            self.win.show()

    def open_default(self):
        subprocess.call(["open", self.src])

    def show_in_finder(self):
        subprocess.call(["open", "-R", self.src])


class SortTypeWidget(QPushButton):
    sort_click = pyqtSignal()

    def __init__(self, parent: QWidget):
        super().__init__()
        self.setFixedWidth(110)
        self.setToolTip(" Сортировка файлов ")

        self.data = {
                "name": "Имя",
                "size": "Размер",
                "modify": "Дата изм.",
                "type": "Тип",
                }

        text = self.data[Config.json_data["sort"]]
        self.setText(text)

        menu = QMenu()
        self.setMenu(menu)

        for k, v in self.data.items():
            action = menu.addAction(v)
            action.triggered.connect(lambda e, k=k: self.action_clicked(k))

    def action_clicked(self, text: str):
        Config.json_data["sort"] = text
        self.setText(self.data[text])
        self.sort_click.emit()


class TopBarWidget(QFrame):
    sort_btn_press = pyqtSignal()
    up_btn_press = pyqtSignal()
    open_btn_press = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.root: str = None
        self.path_labels_list: list = []
        self.setFixedHeight(40)
        self.init_ui()

    def init_ui(self):
        self.grid_layout = QGridLayout()
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.grid_layout)

        l_spacer = QSpacerItem(5, 1)
        self.grid_layout.addItem(l_spacer, 0, 0)

        self.open_btn = QPushButton("Открыть путь")
        self.open_btn.clicked.connect(self.open_btn_cmd)
        self.grid_layout.addWidget(self.open_btn, 0, 1)

        l_spacer = QSpacerItem(1, 1, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.grid_layout.addItem(l_spacer, 0, 2)

        self.up_button = QPushButton(text="↑", parent=self)
        self.up_button.setToolTip(" Перейти на уровень выше ")
        self.up_button.setFixedWidth(60)
        self.up_button.clicked.connect(self.up_btn_press.emit)
        self.grid_layout.addWidget(self.up_button, 0, 3)

        self.sort_widget = SortTypeWidget(parent=self)
        self.sort_widget.sort_click.connect(self.sort_btn_press.emit)
        self.grid_layout.addWidget(self.sort_widget, 0, 4)

        self.ubiv = "↓↑"
        self.vozrast = "↑↓"
        sort_t = self.ubiv if Config.json_data["reversed"] else self.vozrast
        self.sort_button = QPushButton(text=sort_t, parent=self)
        self.sort_button.setToolTip(" Сортировка файлов: по возрастанию / по убыванию ")
        self.sort_button.setFixedWidth(60)
        self.sort_button.clicked.connect(self.on_sort_toggle)
        self.grid_layout.addWidget(self.sort_button, 0, 5)

        r_spacer = QSpacerItem(1, 1, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.grid_layout.addItem(r_spacer, 0, 6)

    def paste_text(self) -> str:
        paste_result = subprocess.run(
            ['pbpaste'],
            capture_output=True,
            text=True,
            check=True
            )
        return paste_result.stdout.strip()
    
    def open_btn_cmd(self):
        path = self.paste_text()
        self.open_btn_press.emit(path)

    def set_path_labels(self):
        return
        for wid in self.path_labels_list:
            wid.deleteLater()
        self.path_labels_list.clear()

        clmn = 4

        splited: list = [i for i in self.root.split(os.sep) if i]
        ln = len(splited)

        data: dict = {
            ln - x - 1: item
            for x, item in enumerate(splited)
            }

        for num, name in data.items():
            clmn += 1
            label = QLabel(name + " >")
            label.mouseReleaseEvent = lambda e, num=num: self.path_label_click(num)
            self.grid_layout.addWidget(label, 0, clmn)
            self.path_labels_list.append(label)

        r_spacer = QSpacerItem(1, 1, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        # self.grid_layout.addItem(r_spacer, 0, clmn)

    def path_label_click(self, num: int):
        for i in range(0, num):
            self.up_btn_press.emit()

    def set_root(self, root: str):
        self.root = root

    def on_sort_toggle(self):
        if Config.json_data["reversed"]:
            Config.json_data["reversed"] = False
            self.sort_button.setText(self.vozrast)
        else:
            Config.json_data["reversed"] = True
            self.sort_button.setText(self.ubiv)
        self.sort_btn_press.emit()


class TreeWidget(QTreeView):
    on_tree_clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        self.model = QFileSystemModel()
        self.model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot)
        self.model.setRootPath("/Volumes")

        self.setModel(self.model)
        self.setRootIndex(self.model.index("/Volumes"))

        self.setHeaderHidden(True)
        for i in range(1, self.model.columnCount()):
            self.setColumnHidden(i, True)
        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.setIndentation(10)

        self.clicked.connect(self.one_clicked)

    def one_clicked(self, index):
        path = self.model.filePath(index)
        self.setCurrentIndex(index)
        self.on_tree_clicked.emit(path)

        if self.isExpanded(index):
            self.collapse(index)
        else:
            self.expand(index)

    def expand_path(self, root: str):
        index = self.model.index(root)
        self.setCurrentIndex(index)
        self.expand(index)


class SimpleFileExplorer(QWidget):
    def __init__(self):
        super().__init__()

        self.clmn_count = 1
        self.finder_items = []
        self.finder_images: dict = {}

        ww, hh = Config.json_data["ww"], Config.json_data["hh"]
        self.resize(ww, hh)
        self.move_to_filepath: str = None

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(0, 0, 0, 0)
        v_lay.setSpacing(0)
        self.setLayout(v_lay)

        self.top_bar = TopBarWidget()
        self.top_bar.sort_btn_press.connect(self.get_finder_items)
        self.top_bar.up_btn_press.connect(self.btn_up_cmd)
        self.top_bar.open_btn_press.connect(self.open_custom_path)
        v_lay.addWidget(self.top_bar)

        splitter_wid = QWidget()
        v_lay.addWidget(splitter_wid)
        splitter_lay = QHBoxLayout()
        splitter_lay.setContentsMargins(10, 0, 10, 10)
        splitter_wid.setLayout(splitter_lay)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.splitterMoved.connect(self.custom_resize_event)
        splitter_lay.addWidget(self.splitter)

        self.left_wid = QWidget()
        self.splitter.addWidget(self.left_wid)
        self.splitter.setStretchFactor(0, 0)

        left_lay = QVBoxLayout()
        left_lay.setContentsMargins(0, 0, 0, 0)
        self.left_wid.setLayout(left_lay)
        
        self.tree_widget = TreeWidget()
        self.tree_widget.on_tree_clicked.connect(self.on_tree_clicked)
        left_lay.addWidget(self.tree_widget)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.splitter.addWidget(self.scroll_area)
        self.splitter.setStretchFactor(1, 1)

        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(5)
        self.scroll_area.setWidget(self.grid_container)

        self.resize_timer = QTimer(parent=self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.setInterval(500)
        self.resize_timer.timeout.connect(self.get_finder_items)

        self.resizeEvent = self.custom_resize_event

        self.load_last_place()
        self.setWindowTitle(Config.json_data["root"])

    def on_tree_clicked(self, root: str):
        Config.json_data["root"] = root
        self.setWindowTitle(root)
        self.get_finder_items()

    def open_custom_path(self, path: str):
        path = "/Volumes/Macintosh HD" + path
        # Учти что без ВОЛУМЕС / ДИСК / ПУТЬ открываться дерево не будет
        # УЧТИ ЧТО ПУТЬ МОЖЕТ БЫТЬ ДО ФАЙЛА

        if not os.path.exists(path):
            return

        if os.path.isfile(path):
            if path.endswith(Config.img_ext):
                self.move_to_filepath = path
            path, _ = os.path.split(path)

        Config.json_data["root"] = path
        # self.tree_widget.collapseAll()
        self.tree_widget.expand_path(path)
        self.setWindowTitle(path)
        self.get_finder_items()

    def btn_up_cmd(self):
        path = os.path.dirname(Config.json_data["root"])
        Config.json_data["root"] = path

        self.tree_widget.expand_path(path)
        self.setWindowTitle(Config.json_data["root"])
        self.get_finder_items()

    def reload_grid_layout(self, event=None):
        ww = Config.json_data["ww"] - self.left_wid.width() - 80
        clmn_count = ww // Config.thumb_size

        if clmn_count < 1:
            clmn_count = 1

        self.clmn_count = clmn_count
        row, col = 0, 0

        for src, filename, size, modified, filetype in self.finder_items:
            thumbnail = Thumbnail(filename, src)
            thumbnail.double_click.connect(
                lambda src=src, wid=thumbnail: self.on_wid_double_clicked(src, wid)
                )
            thumbnail.img_view_closed.connect(lambda src: self.move_to_wid(src))
            self.set_default_image(thumbnail.img_label, "images/file_210.png")

            self.grid_layout.addWidget(thumbnail, row, col)

            col += 1
            if col >= clmn_count:
                col = 0
                row += 1

            self.finder_images[(src, size, modified)] = thumbnail.img_label
            Config.img_viewer_images[src] = thumbnail

        if self.finder_images:
            row_spacer = QSpacerItem(1, 1, QSizePolicy.Minimum, QSizePolicy.Expanding)
            self.grid_layout.addItem(row_spacer, row + 1, 0)
            clmn_spacer = QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum)
            self.grid_layout.addItem(clmn_spacer, 0, clmn_count + 1)

            if self.move_to_filepath:
                self.move_to_wid(self.move_to_filepath)
                self.move_to_filepath = None

            self.load_images()

        else:
            no_images = QLabel(f"{Config.json_data['root']}\nНет изображений")
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0, Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setColumnStretch(0, 1)
            self.grid_layout.setRowStretch(0, 1)

    def load_images(self):
        for i in Storage.load_images_threads:
            i: LoadImagesThread
            i.stop_thread.emit()

            if i.isFinished():
                Storage.load_images_threads.remove(i)

        new_thread = LoadImagesThread(self.finder_images, Config.thumb_size)
        Storage.load_images_threads.append(new_thread)
        new_thread.start()

    def on_wid_double_clicked(self, path: str, wid: Thumbnail):
        wid.setFrameShape(QFrame.Shape.Panel)
        QTimer.singleShot(500, lambda: wid.setFrameShape(QFrame.Shape.NoFrame))
        self.win = WinImageView(self, path)
        self.win.closed.connect(lambda src: self.move_to_wid(src))
        self.win.show()

    def move_to_wid(self, src: str):
        try:
            wid: Thumbnail = Config.img_viewer_images[src]
            wid.setFrameShape(QFrame.Shape.Panel)
            self.scroll_area.ensureWidgetVisible(wid)
            QTimer.singleShot(1000, lambda: self.set_no_frame(wid))
        except (RuntimeError, KeyError):
            pass

    def set_no_frame(self, wid: Thumbnail):
        try:
            wid.setFrameShape(QFrame.Shape.NoFrame)
        except (RuntimeError):
            pass

    def get_finder_items(self):
        self.setDisabled(True)

        Utils.clear_layout(layout=self.grid_layout)
        self.finder_images.clear()

        finder_items = LoadFinderItems(Config.json_data["root"])
        self.finder_items = finder_items.run()

        self.setDisabled(False)
        Config.img_viewer_images.clear()
        self.reload_grid_layout()

    def load_last_place(self):
        root = Config.json_data["root"]

        if root and os.path.exists(root):
            self.tree_widget.expand_path(root)
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
        self.aboutToQuit.connect(self.on_exit)
        self.installEventFilter(self)

    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if a1.type() == QEvent.Type.ApplicationActivate:
            for i in self.topLevelWidgets():
                print(i)
                if type(i) == SimpleFileExplorer:
                    i.show()
                    break
        return False

    def on_exit(self):
        for thread in Storage.load_images_threads:
            thread: LoadImagesThread
            thread.stop_thread.emit()
            thread.wait()

        with open(Config.json_file, 'w') as f:
            json.dump(Config.json_data, f, indent=4, ensure_ascii=False)
