import os
import subprocess
from difflib import SequenceMatcher

from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QFocusEvent, QKeyEvent, QMouseEvent
from PyQt5.QtWidgets import (QButtonGroup, QFrame, QGridLayout, QLabel,
                             QLineEdit, QMenu, QPushButton, QSizePolicy,
                             QSpacerItem, QTabBar, QVBoxLayout, QWidget, QAction)

from cfg import Config
from utils import Utils


class _PathFinderThread(QThread):
    _finished = pyqtSignal(str)

    def __init__(self, src: str):
        super().__init__()
        self.src: str = src
        self.result: str = None
        self.volumes: list = []
        self.exclude = "/Volumes/Macintosh HD/Volumes/"

    def run(self):
        self._path_finder()
        if not self.result:
            self.finished.emit("")
        elif self.result in self.volumes:
            self.finished.emit("")
        elif self.result:
            self.finished.emit(self.result)

    def _path_finder(self):
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


class _SortTypeWidget(QPushButton):
    sort_click = pyqtSignal()

    def __init__(self, parent: QWidget):
        super().__init__()
        self.setFixedWidth(125)
        self.setStyleSheet("text-align: center;")
        self.setToolTip(" Сортировка файлов ")
        
        self.data = {
            0: {"sort": None, "reversed": None, "text": "По убыванию"},

            1: {"sort": "name", "reversed": True, "text": "Имя уб."},
            2: {"sort": "size", "reversed": True, "text": "Размер уб."},
            3: {"sort": "modify", "reversed": True, "text": "Дата уб."},
            4: {"sort": "type", "reversed": True, "text": "Тип уб."},

            5: {"sort": None, "reversed": None, "text": "По возрастанию"},

            6: {"sort": "name", "reversed": False, "text": "Имя возр."},
            7: {"sort": "size", "reversed": False, "text": "Размер возр."},
            8: {"sort": "modify", "reversed": False, "text": "Дата возр."},
            9: {"sort": "type", "reversed": False, "text": "Тип возр."}
            }

        menu = QMenu()
        self.setMenu(menu)

        for k, v in self.data.items():
            action = QAction(parent=self, text=v.get("text"))
            action.triggered.connect(lambda e, v=v: self._action_clicked(v))

            if v.get("sort") == None:
                action.setDisabled(True)

            if v.get("sort") == Config.json_data["sort"]:
                if v.get("reversed") == Config.json_data["reversed"]:
                    self.setText(v.get("text"))

            menu.addAction(action)

    def _action_clicked(self, data: dict):
        Config.json_data["sort"] = data.get("sort")
        Config.json_data["reversed"] = data.get("reversed")
        self.setText(data.get("text"))
        self.sort_click.emit()


class _SearchWidget(QWidget):
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
        self.input_wid.setPlaceholderText("Поиск изображений")
        self.input_wid.setStyleSheet("padding-left: 2px; padding-right: 20px;")
        self.input_wid.setFixedSize(170, 25)
        self.input_wid.mouseReleaseEvent = self._show_templates
        v_lay.addWidget(self.input_wid)

        self.clear_btn = QLabel(parent=self, text="\u2573")
        self.clear_btn.setFixedSize(15, 10)
        self.clear_btn.move(self.input_wid.width() - 20, 8)
        self.clear_btn.hide()
        self.clear_btn.mouseReleaseEvent = lambda e: self.input_wid.clear()

        self.input_wid.textChanged.connect(self._on_text_changed)
        self.search_text: str = None

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(
            lambda: self.start_search_sig.emit(self.search_text)
            )
        
        self.clear_search_sig.connect(self._costil)

    def _costil(self):
        self.input_wid.disconnect()
        self.input_wid.clear()
        self.clear_btn.hide()
        self.input_wid.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self, text):
        self.search_timer.stop()
        if text:
            self.clear_btn.show()
            self.search_text = text
            self.search_timer.start(1000)
        else:
            self.clear_search_sig.emit()
            self.clear_btn.hide()
            self.stop_search_sig.emit()

    def _show_templates(self, a0: QMouseEvent | None) -> None:
        menu = QMenu()

        data = {
            "Найти jpg": str((".jpg", ".jpeg", "jfif")),
            "Найти tiff": str((".tiff", ".tiff")),
            "Найти psd/psb": str((".psd", ".psb")),
            "Найти raw": str((".nef", ".raw")),
            "Найти любые фото": str(Config.img_ext)
            }

        for k, v in data.items():
            action = QAction(parent=self, text=k)
            action.triggered.connect(lambda e, xx=v: self._action_cmd(xx))
            menu.addAction(action)

        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))
    
    def _action_cmd(self, text: str):
        self.input_wid.setText(text)


class _GoWin(QWidget):
    _btn_pressed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Перейти к ...")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint)
        self.setFixedSize(290, 90)
        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 10, 10, 10)
        v_lay.setSpacing(10)
        self.setLayout(v_lay)

        self.input_wid = QLineEdit()
        self.input_wid.setPlaceholderText("Вставьте путь к файлу/папке")
        self.input_wid.setStyleSheet("padding-left: 2px;")
        self.input_wid.setFixedSize(270, 25)
        v_lay.addWidget(self.input_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        go_btn = QPushButton("Перейти")
        go_btn.setFixedWidth(130)
        go_btn.clicked.connect(self._open_path_btn_cmd)
        v_lay.addWidget(go_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def _open_path_btn_cmd(self):
        path: str = self.input_wid.text()

        if not path:
            return

        path: str = os.sep + path.strip().strip(os.sep)

        if os.path.exists(path):
            self._btn_pressed.emit(path)
            self.close()
        else:
            self.path_thread = _PathFinderThread(path)
            self.path_thread._finished.connect(self._finalize)
            self.path_thread.start()

    def _finalize(self, res: str):
        self._btn_pressed.emit(res)
        self.close()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()
        return super().keyPressEvent(a0)


class _GoBtn(QPushButton):
    open_path = pyqtSignal(str)

    def __init__(self):
        super().__init__("Перейти к ...")
        self.clicked.connect(self._open_win)

    def _open_win(self):
        self.win = _GoWin()
        self.win._btn_pressed.connect(self.open_path.emit)
        Utils.center_win(Utils.get_main_win(), self.win)
        self.win.show()


class TopBar(QFrame):
    back_sig = pyqtSignal(str)
    next_sig = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setFixedHeight(40)
        self.clmn = 0

        self.root: str = None
        self.history: list = [Config.json_data["root"]]
        self.current_index: int = 0

        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(5)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.grid_layout)

        self.clmn += 1
        self.back = QPushButton("\u25C0")
        self.back.setFixedWidth(60)
        self.back.clicked.connect(self._back_cmd)
        self.grid_layout.addWidget(self.back, 0, self.clmn)

        self.clmn += 1
        self.next = QPushButton("\u25B6")
        self.next.setFixedWidth(60)
        self.next.clicked.connect(self._next_cmd)
        self.grid_layout.addWidget(self.next, 0, self.clmn)

        self.clmn += 1
        self.grid_layout.setColumnStretch(self.clmn, 10)
        self.grid_layout.addItem(QSpacerItem(1, 1), 0, self.clmn)

        self.clmn += 1
        self.grid_layout.addItem(QSpacerItem(10, 0), 0, self.clmn)

        self.clmn += 1
        self.level_up_btn = QPushButton("Наверх")
        self.grid_layout.addWidget(self.level_up_btn, 0, self.clmn)

        self.clmn += 1
        self.grid_layout.addItem(QSpacerItem(10, 0), 0, self.clmn)

        self.clmn += 1
        self.go_btn = _GoBtn()
        self.grid_layout.addWidget(self.go_btn, 0, self.clmn)

        self.clmn += 1
        self.grid_layout.addItem(QSpacerItem(10, 0), 0, self.clmn)

        self.clmn += 1
        self.sort_widget = _SortTypeWidget(parent=self)
        self.grid_layout.addWidget(self.sort_widget, 0, self.clmn)

        self.clmn += 1
        self.grid_layout.addItem(QSpacerItem(10, 0), 0, self.clmn)

        self.clmn += 1
        self.grid_layout.setColumnStretch(self.clmn, 10)
        self.grid_layout.addItem(QSpacerItem(1, 1), 0, self.clmn)

        self.clmn += 1
        self.search_wid = _SearchWidget()
        self.grid_layout.addWidget(self.search_wid, 0, self.clmn)

    def update_history(self):
        if Config.json_data["root"] not in self.history:
            self.history.append(Config.json_data["root"])
            self.current_index = len(self.history) - 1

        if len(self.history) > 50:
            self.history.pop(0)

    def _back_cmd(self):
        if self.current_index == 0:
            return

        self.current_index -= 1

        try:
            path = self.history[self.current_index]
            self.back_sig.emit(path)
        except IndexError:
            pass

    def _next_cmd(self):
        if self.current_index == len(self.history) - 1:
            return
        
        self.current_index += 1

        try:
            path = self.history[self.current_index]
            self.next_sig.emit(path)
        except IndexError:
            pass