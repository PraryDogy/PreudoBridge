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


class ServersWin(MinMaxDisabledWin):
    title_text = "Подключение к серверу"
    key_server = "server"
    key_login = "login"
    key_pass = "pass"

    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.title_text)
        self.set_modality()
        self.central_layout = QVBoxLayout()
        self.central_layout.setContentsMargins(5, 5, 5, 5)
        self.central_layout.setSpacing(0)
        self.setLayout(self.central_layout)

        self.data: list[dict] = {}
        self.init_data()
        self.init_ui({})
        self.adjustSize()

    def init_data(self):
        json_file = os.path.join(Static.APP_SUPPORT, "servers.json")
        if os.path.exists(json_file):
            with open(json_file, "r", encoding="utf-8") as file:
                self.data = json.load(file.read())

    def init_ui(self, data_dict: dict):
        main_wid = QWidget()
        main_lay = QHBoxLayout()
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        main_wid.setLayout(main_lay)
        self.central_layout.addWidget(main_wid)

        self.server_wid = ULineEdit()
        main_lay.addWidget(self.server_wid)

        self.login_wid = ULineEdit()
        main_lay.addWidget(self.login_wid)

        self.pass_wid = ULineEdit()
        main_lay.addWidget(self.pass_wid)

        # server
        # login
        # pass