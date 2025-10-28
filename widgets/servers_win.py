import json
import os
import subprocess

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QKeyEvent
from PyQt5.QtWidgets import (QAction, QGraphicsOpacityEffect, QGridLayout,
                             QHBoxLayout, QLabel, QPushButton, QSpacerItem,
                             QVBoxLayout, QWidget)

from cfg import Static
from system.items import BaseItem
from system.shared_utils import SharedUtils
from system.tasks import ImgRes, MultipleItemsInfo, UThreadPool

from ._base_widgets import MinMaxDisabledWin, ULineEdit, UMenu
from .actions import CopyText, RevealInFinder


class ServerLoginWidget(QWidget):
    placeholder_text = "Сервер, логин, пароль"

    def __init__(self, server: str, login: str, pass_: str):
        super().__init__()

        main_lay = QHBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)

        combo_wid = ULineEdit()
        if server:
            combo_wid.setText(f"{server}, {login}, {pass_}")
        combo_wid.setPlaceholderText(self.placeholder_text)

        main_lay.addWidget(combo_wid)

    def get_data(self):
        return [
            i.strip()
            for i in self.findChild(ULineEdit).text().split(",")
        ]


class ServersWin(MinMaxDisabledWin):
    title_text = "Подключение к серверу"
    connect_text = "Подкл."
    cancel_text = "Отмена"
    json_file = os.path.join(Static.APP_SUPPORT, "servers.json")

    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.title_text)
        self.set_modality()
        self.setFixedWidth(300)
        self.central_layout = QVBoxLayout()
        self.central_layout.setContentsMargins(5, 5, 5, 5)
        self.central_layout.setSpacing(10)
        self.setLayout(self.central_layout)
        self.data: list[tuple] = {}
        self.empty_data = ("", "", "")
        self.init_data()
        for i in self.data:
            self.init_servers(i)
        self.init_servers(self.empty_data)

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

    def init_servers(self, server_data: tuple):
        server, login, pass_ = server_data
        main_wid = ServerLoginWidget(server, login, pass_)
        self.central_layout.addWidget(main_wid)

    def connect_cmd(self):

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
        for i in self.findChildren(ServerLoginWidget):
            data = i.get_data()
            if data and len(data) == 3:
                all_data.append(data)
        with open(self.json_file, "w", encoding="utf-8") as file:
            json.dump(all_data, file, indent=4, ensure_ascii=False)

    def mouseReleaseEvent(self, a0):
        self.setFocus()
        return super().mouseReleaseEvent(a0)