import os
import subprocess
from difflib import SequenceMatcher

from PyQt5.QtCore import QThread, QTimer, pyqtSignal, Qt
from PyQt5.QtWidgets import (QFrame, QGridLayout, QLabel, QLineEdit, QMenu,
                             QPushButton, QSizePolicy, QSpacerItem,
                             QVBoxLayout, QWidget, QTabBar, QButtonGroup)

from cfg import Config


class PathFinderThread(QThread):
    finished = pyqtSignal(str)

    def __init__(self, src: str):
        super().__init__()
        self.src: str = src
        self.result: str = None
        self.volumes: list = []
        self.exclude = "/Volumes/Macintosh HD/Volumes/"

    def run(self):
        self.path_finder()
        if not self.result:
            self.finished.emit("")
        elif self.result in self.volumes:
            self.finished.emit("")
        elif self.result:
            self.finished.emit(self.result)

    def path_finder(self):
        src = os.sep + self.src.replace("\\", os.sep).strip().strip(os.sep)
        src_splited = [i for i in src.split(os.sep) if i]

        self.volumes = [
            os.path.join("/Volumes", i)
            for i in os.listdir("/Volumes")
            ]

        volumes_extra = [
            os.path.join(vol, *extra.strip().split(os.sep))
            for extra in Config.json_data["extra_paths"]
            for vol in self.volumes
            ]
        
        self.volumes.extend(volumes_extra)

        # обрезаем входящий путь каждый раз на 1 секцию с конца
        cut_paths: list = [
                os.path.join(*src_splited[:i])
                for i in range(len(src_splited) + 1)
                if src_splited[:i]
                ]

        # обрезаем каждый путь на 1 секцию с начала и прибавляем элементы из volumes
        all_posible_paths: list = []

        for p_path in sorted(cut_paths, key=len, reverse=True):
            p_path_split = [i for i in p_path.split(os.sep) if i]
            
            for share in self.volumes:
                for i in range(len(p_path_split) + 1):

                    all_posible_paths.append(
                        os.path.join(share, *p_path_split[i:])
                        )

        # из всех полученных возможных путей ищем самый подходящий существующий путь
        for i in sorted(all_posible_paths, key=len, reverse=True):
            if self.exclude in i:
                print("ignore strange folder", self.exclude)
                continue
            if os.path.exists(i):
                self.result = i
                break

        # смотрим совпадает ли последняя секция входящего и полученного пути
        tail = []

        if self.result:
            result_tail = self.result.split(os.sep)[-1]
            if src_splited[-1] != result_tail:
                try:
                    tail = src_splited[src_splited.index(result_tail) + 1:]
                except ValueError:
                    return

        # пытаемся найти секции пути, написанные с ошибкой
        for a in tail:
            dirs = [x for x in os.listdir(self.result)]

            for b in dirs:
                matcher = SequenceMatcher(None, a, b).ratio()
                if matcher >= 0.85:
                    self.result = os.path.join(self.result, b)
                    break


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


class SearchWidget(QWidget):
    start_search_sig = pyqtSignal(str)
    stop_search_sig = pyqtSignal()
    clear_search_sig = pyqtSignal()

    def __init__(self):
        super().__init__()

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(0, 0, 0, 0)
        v_lay.setSpacing(0)
        self.setLayout(v_lay)

        self.input_wid = QLineEdit()
        self.input_wid.setPlaceholderText("Поиск")
        self.input_wid.setStyleSheet("padding-left: 2px;")
        self.input_wid.setFixedSize(200, 25)
        v_lay.addWidget(self.input_wid)

        self.clear_btn = QLabel(parent=self, text="⛌")
        self.clear_btn.setFixedSize(15, 10)
        self.clear_btn.move(180, 8)
        self.clear_btn.hide()
        self.clear_btn.mouseReleaseEvent = lambda e: self.input_wid.clear()

        self.input_wid.textChanged.connect(self.on_text_changed)
        self.search_text: str = None

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(
            lambda: self.start_search_sig.emit(self.search_text)
            )
        
        self.clear_search_sig.connect(self.costil)

    def costil(self):
        self.input_wid.disconnect()
        self.input_wid.clear()
        self.clear_btn.hide()
        self.input_wid.textChanged.connect(self.on_text_changed)

    def on_text_changed(self, text):
        if text:
            self.clear_btn.show()
            self.search_text = text
            self.search_timer.stop()
            self.search_timer.start(1000)
        else:
            self.clear_btn.hide()
            self.stop_search_sig.emit()


class TopBar(QFrame):
    sort_vozrast_btn_press = pyqtSignal()
    open_path_btn_press = pyqtSignal(str)
    back_sig = pyqtSignal(str)
    next_sig = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setFixedHeight(40)

        self.root: str = None
        self.history: list = [Config.json_data["root"]]
        self.current_index: int = 0

        self.init_ui()

    def init_ui(self):
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(5)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.grid_layout)

        self.back = QPushButton("⏴")
        self.back.setFixedWidth(60)
        self.back.clicked.connect(self.back_cmd)
        self.grid_layout.addWidget(self.back, 0, 0)

        self.next = QPushButton("⏵")
        self.next.setFixedWidth(60)
        self.next.clicked.connect(self.next_cmd)
        self.grid_layout.addWidget(self.next, 0, 1)

        self.grid_layout.setColumnStretch(2, 10)
        self.grid_layout.addItem(QSpacerItem(1, 1), 0, 2)

        self.open_btn = QPushButton("Открыть путь")
        self.open_btn.clicked.connect(self.open_path_btn_cmd)
        self.grid_layout.addWidget(self.open_btn, 0, 3)

        self.grid_layout.addItem(QSpacerItem(10, 0), 0, 4)

        self.sort_widget = SortTypeWidget(parent=self)
        self.sort_widget.sort_click.connect(self.sort_vozrast_btn_press.emit)
        self.grid_layout.addWidget(self.sort_widget, 0, 5)

        self.grid_layout.addItem(QSpacerItem(10, 0), 0, 6)

        self.ubiv = "↓↑"
        self.vozrast = "↑↓"
        sort_t = self.ubiv if Config.json_data["reversed"] else self.vozrast
        self.sort_vozrast_button = QPushButton(text=sort_t, parent=self)
        self.sort_vozrast_button.setToolTip(" Сортировка файлов: по возрастанию / по убыванию ")
        self.sort_vozrast_button.setFixedWidth(60)
        self.sort_vozrast_button.clicked.connect(self.on_sort_toggle)
        self.grid_layout.addWidget(self.sort_vozrast_button, 0, 7)

        self.grid_layout.setColumnStretch(8, 10)
        self.grid_layout.addItem(QSpacerItem(1, 1), 0, 8)

        self.search_wid = SearchWidget()
        self.grid_layout.addWidget(self.search_wid, 0, 9)

    def paste_text(self) -> str:
        paste_result = subprocess.run(
            ['pbpaste'],
            capture_output=True,
            text=True,
            check=True
            )
        return paste_result.stdout.strip()
    
    def open_path_btn_cmd(self):
        path = self.paste_text()
        self.path_thread = PathFinderThread(path)
        self.path_thread.finished.connect(
            lambda res: self.open_path_btn_press.emit(res)
            )
        
        self.path_thread.start()

    def on_sort_toggle(self):
        if Config.json_data["reversed"]:
            Config.json_data["reversed"] = False
            self.sort_vozrast_button.setText(self.vozrast)
        else:
            Config.json_data["reversed"] = True
            self.sort_vozrast_button.setText(self.ubiv)
        self.sort_vozrast_btn_press.emit()

    def update_history(self):
        self.history.append(Config.json_data["root"])
        self.current_index = len(self.history) - 1

        if len(self.history) > 50:
            self.history.pop(0)

    def back_cmd(self):
        self.current_index -= 1

        try:
            path = self.history[self.current_index]
            self.back_sig.emit(path)
            if self.current_index == 0:
                self.current_index = len(self.history)
        except IndexError:
            pass

    def next_cmd(self):
        self.current_index += 1

        try:
            path = self.history[self.current_index]
            self.next_sig.emit(path)
            if self.current_index == len(self.history):
                self.current_index = 0
        except IndexError:
            print("index error")
