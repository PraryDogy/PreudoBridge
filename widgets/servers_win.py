import json
import os
import subprocess

from PyQt5.QtCore import QPoint, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QKeyEvent
from PyQt5.QtWidgets import (QAction, QGraphicsOpacityEffect, QGridLayout,
                             QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                             QMenu, QPushButton, QSpacerItem, QVBoxLayout,
                             QWidget)

from cfg import Static
from system.items import BaseItem
from system.shared_utils import SharedUtils
from system.tasks import ImgRes, MultipleItemsInfo, UThreadPool

from ._base_widgets import MinMaxDisabledWin, ULineEdit, UMenu
from .actions import CopyText, RevealInFinder


class ServersWidget(QWidget):
    def __init__(self, data: list[list[str]]):
        super().__init__()

        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.open_menu)

        for server, login, password in data:
            item = QListWidgetItem(f"{server}, {login}, {password}")
            item.setSizeHint(item.sizeHint().expandedTo(QSize(0, 25)))
            self.list_widget.addItem(item)

        layout.addWidget(self.list_widget)

    def open_menu(self, pos: QPoint):
        item = self.list_widget.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)
        delete_action = QAction("Удалить", self)
        delete_action.triggered.connect(lambda: self.delete_item(item))
        menu.addAction(delete_action)
        menu.exec_(self.list_widget.mapToGlobal(pos))

    def delete_item(self, item: QListWidgetItem):
        row = self.list_widget.row(item)
        self.list_widget.takeItem(row)


class ServersWin(MinMaxDisabledWin):
    title_text = "Подключение к серверу"
    connect_text = "Подкл."
    cancel_text = "Отмена"
    new_server_text = "Сервер, логин, пароль"
    json_file = os.path.join(Static.APP_SUPPORT, "servers.json")

    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.title_text)
        self.set_modality()
        self.setFixedWidth(300)
        self.data: list[tuple] = []
        self.init_data()

        self.central_layout = QVBoxLayout()
        self.central_layout.setContentsMargins(5, 5, 5, 5)
        self.central_layout.setSpacing(10)
        self.setLayout(self.central_layout)

        self.new_server = ULineEdit()
        self.new_server.setPlaceholderText(self.new_server_text)
        self.central_layout.addWidget(self.new_server)

        self.servers_widget = ServersWidget(self.data)
        self.central_layout.addWidget(self.servers_widget)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(10)
        btn_connect = QPushButton(self.connect_text)
        btn_cancel = QPushButton(self.cancel_text)
        btn_connect.clicked.connect(self.connect_cmd)
        btn_cancel.clicked.connect(
            lambda: (self.save_cmd(), self.deleteLater())
        )
        btn_connect.setFixedWidth(90)
        btn_cancel.setFixedWidth(90)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_connect)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addStretch()

        self.central_layout.addLayout(btn_layout)

        self.adjustSize()
        self.setFocus()

    def init_data(self):
        if os.path.exists(self.json_file):
            with open(self.json_file, "r", encoding="utf-8") as file:
                self.data = json.load(file)

    def connect_cmd(self):
        return

        def open_smb(data: list[str]):
            if data and len(data) == 3:
                server, login, pass_ = data
                cmd = f"smb://{login}:{pass_}@{server}"
                subprocess.run(["open", cmd])
                return cmd

        for i in self.findChildren(ServerLoginWidget):
            open_smb(i.get_data())

    def save_cmd(self):
        all_data = []

        # Получаем все элементы из QListWidget
        for i in range(self.servers_widget.list_widget.count()):
            item = self.servers_widget.list_widget.item(i)
            parts = [p.strip() for p in item.text().split(",")]
            all_data.append(parts)

        # Сохраняем в JSON
        with open(self.json_file, "w", encoding="utf-8") as file:
            json.dump(all_data, file, indent=4, ensure_ascii=False)

    def mouseReleaseEvent(self, a0):
        self.setFocus()
        return super().mouseReleaseEvent(a0)
    
    def keyPressEvent(self, a0):
        self.save_cmd()
        self.deleteLater()
        return super().keyPressEvent(a0)