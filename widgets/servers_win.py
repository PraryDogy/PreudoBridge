import json
import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QKeyEvent
from PyQt5.QtWidgets import (QAction, QGraphicsOpacityEffect, QGridLayout,
                             QHBoxLayout, QLabel, QSpacerItem, QVBoxLayout,
                             QWidget)

from cfg import Static
from system.items import BaseItem
from system.shared_utils import SharedUtils
from system.tasks import ImgRes, MultipleItemsInfo, UThreadPool

from ._base_widgets import MinMaxDisabledWin, ULineEdit, UMenu
from .actions import CopyText, RevealInFinder


class ServerLoginWidget(QWidget):
    def __init__(self, server: str, login: str, pass_: str):
        super().__init__()

        main_lay = QHBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        server_wid = ULineEdit()
        login_wid = ULineEdit()
        pass_wid = ULineEdit()

        server_wid.setText(server)
        login_wid.setText(login)
        pass_wid.setText(pass_)

        main_lay.addWidget(server_wid)
        main_lay.addWidget(login_wid)
        main_lay.addWidget(pass_wid)

    def get_data(self):
        return (
            i.text()
            for i in self.findChildren(ULineEdit)
        )


class ServersWin(MinMaxDisabledWin):
    title_text = "Подключение к серверу"

    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.title_text)
        self.set_modality()
        self.central_layout = QVBoxLayout()
        self.central_layout.setContentsMargins(5, 5, 5, 5)
        self.central_layout.setSpacing(0)
        self.setLayout(self.central_layout)
        self.data: list[tuple] = {}
        self.empty_data = ("", "", "")
        self.init_data()
        for i in self.data:
            self.init_ui(i)
        self.init_ui(self.empty_data)
        self.adjustSize()

    def init_data(self):
        json_file = os.path.join(Static.APP_SUPPORT, "servers.json")
        if os.path.exists(json_file):
            with open(json_file, "r", encoding="utf-8") as file:
                self.data = json.load(file.read())

    def init_ui(self, server_data: tuple):
        server, login, pass_ = server_data
        main_wid = ServerLoginWidget(server, login, pass_)
        self.central_layout.addWidget(main_wid)
