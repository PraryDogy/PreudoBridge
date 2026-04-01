import subprocess
from dataclasses import dataclass

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QAction, QHBoxLayout, QLabel, QListWidget,
                             QListWidgetItem, QSpacerItem, QVBoxLayout,
                             QWidget)

from ._base_widgets import MinMaxDisabledWin, SmallBtn, ULineEdit, UMenu
from .warn_win import WinQuestion

# from cfg import Cfg
# from system.servers import Servers



@dataclass(slots=True)
class ServerItem:
    server: str
    login: str
    password: str


class ServerListItem(QListWidgetItem):
    def __init__(self, parent: QListWidget, text: str, server_item: ServerItem):
        super().__init__(parent=parent, text=text)
        self.server_item = server_item


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
        self.win_warn = WinQuestion(
            title="Внимание",
            text="Вы уверены, что хотите удалить данные сервера?"
        )
        self.win_warn.ok_clicked.connect(
            lambda: self.remove_server.emit(server_item)
        )
        self.win_warn.ok_clicked.connect(
            self.win_warn.deleteLater
        )
        self.win_warn.center_to_parent(self.window())
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

        self.menu_ = UMenu(a0)

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

        self.menu_.show_menu()


class ServerLabel(QLabel):
    def __init__(self, text: str):
        super().__init__(text=text)
        self.setStyleSheet("padding-left: 1px;")


class LoginWin(MinMaxDisabledWin):
    ok_pressed = pyqtSignal(ServerItem)
    ww = 300

    def __init__(self, server_item: ServerItem = None):

        super().__init__()
        self.setFixedWidth(self.ww)
        self.central_layout = QVBoxLayout()
        self.central_layout.setContentsMargins(5, 5, 5, 5)
        self.centralWidget().setLayout(self.central_layout)
        self.central_layout.setSpacing(5)

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
            self.server.setText(server_item.server)
            self.login.setText(server_item.login)
            self.pass_.setText(server_item.password)

        self.adjustSize()

        self.eye_svg = EyeSvg()
        self.eye_svg.setParent(self.pass_)
        self.eye_svg.move(
            self.ww - 50,
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
        if self.server.text() and self.login.text() and self.pass_.text():
            server_item = ServerItem(
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


class ServersWin(MinMaxDisabledWin):
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
        return
        for server, login, pass_ in Servers.items:
            server_item = ServerItem(
                server=server,
                login=login,
                password=pass_
            )
            list_item = ServerListItem(
                parent=self.v_list,
                text=server,
                server_item=server_item
            )
            self.v_list.addItem(list_item)
        
        if Servers.items:
            self.v_list.setCurrentRow(0)


    def show_login_win(self, server_item: ServerItem = None):

        def ok_pressed(new_server_item: ServerItem):
            return
            if server_item:
                self.remove_cmd(server_item)
            Servers.items.append([
                new_server_item.server,
                new_server_item.login,
                new_server_item.password
            ])
            Servers.write_json_data()
            list_item = ServerListItem(
                parent=self.v_list,
                text=new_server_item.server,
                server_item=new_server_item
            )
            self.v_list.addItem(list_item)

        self.login_win = LoginWin(server_item)
        self.login_win.ok_pressed.connect(ok_pressed)
        self.login_win.center(self.window())
        self.login_win.show()

    def remove_cmd(self, server_item: ServerItem):
        return
        Servers.items.remove([
            server_item.server,
            server_item.login,
            server_item.password
        ])
        Servers.write_json_data()
        for i in range(self.v_list.count()):
            item = self.v_list.item(i)
            if not item:
                continue
            current = (
                item.server_item.server,
                item.server_item.login,
                item.server_item.password
            )
            target = (
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
    