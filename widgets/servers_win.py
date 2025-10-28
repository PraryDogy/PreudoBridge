import json
import os
import subprocess

from PyQt5.QtCore import QPoint, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QKeyEvent
from PyQt5.QtWidgets import (QAction, QButtonGroup, QGraphicsOpacityEffect,
                             QGridLayout, QHBoxLayout, QLabel, QListWidget,
                             QListWidgetItem, QMenu, QPushButton, QSpacerItem,
                             QVBoxLayout, QWidget)

from cfg import Static
from system.items import BaseItem
from system.shared_utils import SharedUtils
from system.tasks import ImgRes, MultipleItemsInfo, UThreadPool

from ._base_widgets import MinMaxDisabledWin, ULineEdit, UMenu
from .actions import CopyText, RevealInFinder


class ServersWidget(QListWidget):
    def __init__(self, data: list[list[str]]):
        super().__init__()
        for server, login, password in data:
            item = QListWidgetItem(f"{server}, {login}, {password}")
            item.setSizeHint(QSize(0, 25))
            self.addItem(item)


class ServersWin(MinMaxDisabledWin):
    title_text = "Подключение к серверу"
    connect_text = "Подкл."
    new_server_text = "Сервер, логин, пароль"
    json_file = os.path.join(Static.APP_SUPPORT, "servers.json")

    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.title_text)
        self.set_modality()
        self.setFixedWidth(300)

        # Загрузка данных
        self.data: list[list[str]] = []
        self.init_data()

        # Layout
        self.central_layout = QVBoxLayout()
        self.central_layout.setContentsMargins(5, 5, 5, 5)
        self.central_layout.setSpacing(10)
        self.setLayout(self.central_layout)

        # QLineEdit для нового сервера
        self.new_server = ULineEdit()
        self.new_server.setPlaceholderText(self.new_server_text)
        self.central_layout.addWidget(self.new_server)

        # QListWidget
        self.servers_widget = ServersWidget(self.data)
        self.central_layout.addWidget(self.servers_widget)

        # Кнопки
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(5)

        # + и - слева
        btn_add = QPushButton("+")
        btn_add.setFixedWidth(50)
        btn_add.clicked.connect(self.add_server)

        btn_remove = QPushButton("–")
        btn_remove.setFixedWidth(50)
        btn_remove.clicked.connect(self.remove_server)

        # Connect справа
        btn_connect = QPushButton(self.connect_text)
        btn_connect.setFixedWidth(90)
        btn_connect.clicked.connect(self.connect_cmd)

        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_remove)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_connect)

        self.central_layout.addWidget(btn_widget)

        self.adjustSize()
        self.setFocus()

    # Загрузка данных из JSON
    def init_data(self):
        if os.path.exists(self.json_file):
            with open(self.json_file, "r", encoding="utf-8") as f:
                self.data = json.load(f)

    def add_server(self):
        text = self.new_server.text().strip()
        if not text:
            return

        parts = [p.strip() for p in text.split(",")]
        if len(parts) != 3:
            return  # неправильный формат

        server, login, password = parts

        # Добавляем в QListWidget
        item_text = f"{server}, {login}, {password}"
        item = QListWidgetItem(item_text)
        item.setSizeHint(QSize(0, 25))
        self.servers_widget.addItem(item)

        # Добавляем в self.data
        self.data.append(parts)

        # Очищаем QLineEdit
        self.new_server.clear()

        # Сохраняем
        self.save_cmd()

    def remove_server(self):
        item = self.servers_widget.currentItem()
        if not item:
            return

        parts = [p.strip() for p in item.text().split(",")]

        # Удаляем из QListWidget
        row = self.servers_widget.row(item)
        self.servers_widget.takeItem(row)

        # Удаляем из self.data
        if parts in self.data:
            self.data.remove(parts)

        # Сохраняем
        self.save_cmd()

    def save_cmd(self):
        all_data = []
        for i in range(self.servers_widget.count()):
            item = self.servers_widget.item(i)
            parts = [p.strip() for p in item.text().split(",")]
            all_data.append(parts)

        with open(self.json_file, "w", encoding="utf-8") as file:
            json.dump(all_data, file, indent=4, ensure_ascii=False)

    def connect_cmd(self):
        for server, login, password in self.data:
            cmd = f"smb://{login}:{password}@{server}"
            subprocess.run(["open", cmd])
        self.deleteLater()

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()
        return super().keyPressEvent(a0)