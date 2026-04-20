import json
import os
import subprocess
from dataclasses import dataclass

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QAction, QHBoxLayout, QLabel, QListWidget,
                             QListWidgetItem, QSpacerItem, QVBoxLayout,
                             QWidget)

from cfg import Static

from ._base_widgets import WinMinCloseOnly, SmallBtn, ULineEdit, UMenu
from .warn_win import ConfirmWindow

# from cfg import Cfg
# from system.servers import Servers


class Servers:
    items = []
    filepath = os.path.join(Static.app_dir, "servers.json")

    @classmethod
    def json_to_app(cls):
        try:
            with open(cls.filepath, "r", encoding="utf-8") as f:
                server_list: list[list] = json.load(f)
            for i in server_list:
                if len(i) == 3:
                    i.insert(0, "Задайте псевдоним")
                Servers.items.append(i)
        except Exception as e:
            print("Servers json to app error", e)
    
    @classmethod
    def write_json_data(cls):
        with open(cls.filepath, "w", encoding="utf-8") as file:
            json.dump(cls.items, file, indent=4, ensure_ascii=False)


@dataclass(slots=True)
class ServerItem:
    alias: str
    server: str
    login: str
    password: str


class ServerListItem(QListWidgetItem):
    iconpath = "./images/next.svg"
    def __init__(self, parent: QListWidget, text: str, server_item: ServerItem):
        super().__init__(text, parent)
        self.server_item = server_item
        self.setSizeHint(QSize(0, 25))


class EyeSvg(QSvgWidget):
    eye_on = "./images/eye_on.svg"
    eye_off = "./images/eye_off.svg"

    def __init__(self):
        super().__init__()
        self.setFixedSize(20, 20)
        self.load(self.eye_off)

    def enterEvent(self, a0):
        self.setCursor(
            Qt.CursorShape.ArrowCursor
        )
        return super().enterEvent(a0)
    

class ServerList(QListWidget):
    edit_server = pyqtSignal(ServerItem)
    remove_server = pyqtSignal(ServerItem)
    connect_server = pyqtSignal()

    def __init__(self, parent = None):
        super().__init__(parent)

    def remove_cmd(self, server_item: ServerItem):
        self.win_warn = ConfirmWindow(
            text="Вы уверены, что хотите удалить данные сервера?"
        )
        self.win_warn.ok_clicked.connect(
            lambda: self.remove_server.emit(server_item)
        )
        self.win_warn.ok_clicked.connect(
            self.win_warn.deleteLater
        )
        self.win_warn.center(self.window())
        self.win_warn.show()

    def mouseDoubleClickEvent(self, e):
        list_item: ServerListItem = self.itemAt(e.pos())
        if list_item:
            self.connect_server.emit()
        return super().mouseDoubleClickEvent(e)

    def contextMenuEvent(self, a0):
        list_item: ServerListItem = self.itemAt(a0.pos())
        if not list_item:
            return

        self.menu_ = UMenu()

        connect = QAction("Подключиться", self.menu_)
        connect.triggered.connect(self.connect_server.emit)
        self.menu_.addAction(connect)

        self.menu_.addSeparator()

        edit = QAction("Редактировать", self.menu_)
        edit.triggered.connect(
            lambda: self.edit_server.emit(list_item.server_item)
        )
        self.menu_.addAction(edit)

        rem = QAction("Удалить", self.menu_)
        rem.triggered.connect(
            lambda: self.remove_cmd(list_item.server_item)
        )
        self.menu_.addAction(rem)

        self.menu_.show_under_cursor()


class ServerLabel(QLabel):
    def __init__(self, text: str):
        super().__init__(text=text)
        self.setStyleSheet("padding-left: 1px;")


class WinLogin(WinMinCloseOnly):
    ok_pressed = pyqtSignal(ServerItem)
    ww = 300

    def __init__(self, server_item: ServerItem = None):

        super().__init__()
        self.setFixedWidth(self.ww)
        self.central_layout = QVBoxLayout()
        self.central_layout.setContentsMargins(5, 5, 5, 5)
        self.centralWidget().setLayout(self.central_layout)
        self.central_layout.setSpacing(5)

        alias_label = ServerLabel(text="Псевдоним")
        self.central_layout.addWidget(alias_label)

        self.alias = ULineEdit()
        self.alias.setPlaceholderText("Псевдоним")
        self.central_layout.addWidget(self.alias)

        server_label = ServerLabel(text="Сервер")
        self.central_layout.addWidget(server_label)

        self.server = ULineEdit()
        self.server.setPlaceholderText("Сервер")
        self.central_layout.addWidget(self.server)

        login_label = ServerLabel(text="Логин")
        self.central_layout.addWidget(login_label)

        self.login = ULineEdit()
        self.login.setPlaceholderText("Логин")
        self.central_layout.addWidget(self.login)

        self.central_layout.addSpacerItem(QSpacerItem(0, 10))

        pass_label = ServerLabel(text="Пароль")
        self.central_layout.addWidget(pass_label)

        self.pass_ = ULineEdit()
        self.pass_.setEchoMode(ULineEdit.EchoMode.Password)
        self.pass_.setPlaceholderText("Пароль")
        self.central_layout.addWidget(self.pass_)
        self.pass_.setStyleSheet(
            "padding-right: 33px;"
        )

        self.central_layout.addSpacerItem(QSpacerItem(0, 10))

        self.btn_layout = QHBoxLayout()
        self.btn_layout.setSpacing(10)
        self.central_layout.addLayout(self.btn_layout)

        self.btn_layout.addStretch()

        self.ok_btn = SmallBtn("Ок")
        self.ok_btn.clicked.connect(self.ok_cmd)
        self.ok_btn.setFixedWidth(90)
        self.btn_layout.addWidget(self.ok_btn)

        self.cancel_btn = SmallBtn("Отмена")
        self.cancel_btn.setFixedWidth(90)
        self.cancel_btn.clicked.connect(self.deleteLater)
        self.btn_layout.addWidget(self.cancel_btn)

        self.btn_layout.addStretch()

        if server_item:
            self.alias.setText(server_item.alias)
            self.server.setText(server_item.server)
            self.login.setText(server_item.login)
            self.pass_.setText(server_item.password)

        self.adjustSize()

        self.eye_svg = EyeSvg()
        self.eye_svg.setParent(self.pass_)
        self.eye_svg.move(
            self.ww - 40,
            5
        )
        self.eye_svg.show()
        self.eye_svg.mouseReleaseEvent = self.show_hide_pass

    def show_hide_pass(self, *args):
        if self.pass_.echoMode() == ULineEdit.EchoMode.Password:
            self.pass_.setEchoMode(ULineEdit.EchoMode.Normal)
            self.eye_svg.load(self.eye_svg.eye_on)
        else:
            self.pass_.setEchoMode(ULineEdit.EchoMode.Password)
            self.eye_svg.load(self.eye_svg.eye_off)

    def ok_cmd(self):
        stmt = all((
            self.alias.text(),
            self.server.text(),
            self.login.text(),
            self.pass_.text()
        ))
        if stmt:
            server_item = ServerItem(
                alias=self.alias.text(),
                server=self.server.text(),
                login=self.login.text(),
                password=self.pass_.text()
            )
            self.ok_pressed.emit(server_item)
            self.deleteLater()

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()
        elif a0.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            self.ok_cmd()
        return super().keyPressEvent(a0)


class WinServers(WinMinCloseOnly):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Подключиться к серверу")
        self.setFixedSize(350, 250)

        self.central_layout = QVBoxLayout()
        self.centralWidget().setLayout(self.central_layout)
        self.central_layout.setContentsMargins(5, 5, 5, 5)
        self.central_layout.setSpacing(10)

        favs = ServerLabel("Избранное")
        self.central_layout.addWidget(favs)

        self.v_list = ServerList()
        self.v_list.edit_server.connect(self.show_login_win)
        self.v_list.remove_server.connect(self.remove_cmd)
        self.v_list.connect_server.connect(self.connect_cmd)
        self.central_layout.addWidget(self.v_list)

        # Кнопки
        btn_widget = QWidget()
        btn_layout = QHBoxLayout()
        btn_widget.setLayout(btn_layout)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(10)
        self.central_layout.addWidget(btn_widget)

        btn_layout.addStretch()

        btn_add = SmallBtn("Добавить")
        btn_add.setFixedWidth(90)
        btn_add.clicked.connect(self.show_login_win)
        btn_layout.addWidget(btn_add)

        btn_connect = SmallBtn("Подкл.")
        btn_connect.setFixedWidth(90)
        btn_connect.clicked.connect(self.connect_cmd)
        btn_layout.addWidget(btn_connect)

        self.adjustSize()
        self.setFocus()
        self.init_data()

    # Загрузка данных из JSON
    def init_data(self):
        for alias, server, login, pass_ in Servers.items:
            server_item = ServerItem(
                alias=alias,
                server=server,
                login=login,
                password=pass_
            )
            list_item = ServerListItem(
                parent=self.v_list,
                text=f"{server} ({alias})",
                server_item=server_item
            )
            self.v_list.addItem(list_item)
        
        if Servers.items:
            self.v_list.setCurrentRow(0)


    def show_login_win(self, server_item: ServerItem = None):

        def ok_pressed(new_server_item: ServerItem):
            if server_item:
                self.remove_cmd(server_item)
            Servers.items.append([
                new_server_item.alias,
                new_server_item.server,
                new_server_item.login,
                new_server_item.password
            ])
            Servers.write_json_data()
            list_item = ServerListItem(
                parent=self.v_list,
                text=f"{new_server_item.server} ({new_server_item.alias})",
                server_item=new_server_item
            )
            
            self.v_list.addItem(list_item)
            self.v_list.setCurrentItem(list_item)

        self.login_win = WinLogin(server_item)
        self.login_win.ok_pressed.connect(ok_pressed)
        self.login_win.center(self.window())
        self.login_win.show()

    def remove_cmd(self, server_item: ServerItem):
        Servers.items.remove([
            server_item.alias,
            server_item.server,
            server_item.login,
            server_item.password
        ])
        Servers.write_json_data()
        for i in range(self.v_list.count()):
            item: ServerListItem = self.v_list.item(i)
            if not item:
                continue
            current = (
                item.server_item.alias,
                item.server_item.server,
                item.server_item.login,
                item.server_item.password
            )
            target = (
                server_item.alias,
                server_item.server,
                server_item.login,
                server_item.password
            )
            if current == target:
                self.v_list.takeItem(i)

    def connect_cmd(self):
        list_item: ServerListItem = self.v_list.currentItem()
        if not list_item:
            return
        server_item = list_item.server_item
        s, l, p = server_item.server, server_item.login, server_item.password
        smb = "smb://"
        ip = s.split(smb)[-1]
        cmd = f"{smb}{l}:{p}@{ip}"
        subprocess.run(["open", cmd])

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()
        return super().keyPressEvent(a0)


Servers.json_to_app()