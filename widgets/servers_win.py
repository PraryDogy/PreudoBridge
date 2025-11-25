import json
import os
import subprocess

from PyQt5.QtCore import QModelIndex, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QStandardItem, QStandardItemModel
from PyQt5.QtWidgets import (QApplication, QHBoxLayout, QHeaderView,
                             QListWidget, QListWidgetItem, QMenu, QPushButton,
                             QTableView, QVBoxLayout, QWidget)

from cfg import Static

from ._base_widgets import MinMaxDisabledWin, ULineEdit, UMenu
from system.shared_utils import SharedUtils

class ServersWidget(QTableView):
    remove = pyqtSignal(object)

    def __init__(self, data: list[list[str]]):
        super().__init__()

        self.model_ = QStandardItemModel(0, 3, self)
        self.model_.setHorizontalHeaderLabels(["Сервер", "Логин", "Пароль"])
        self.setModel(self.model_)

        for row in data:
            items = [QStandardItem(str(val)) for val in row]
            for item in items:
                item.setEditable(False)
            self.model_.appendRow(items)

        # Настройки таблицы
        header = self.horizontalHeader()

        # Сначала выставляем авто-ширину по содержимому
        header.setSectionResizeMode(QHeaderView.ResizeToContents)

        # Потом немного увеличиваем, чтобы не было сжатия
        self.resizeColumnsToContents()
        self.horizontalHeader().setStretchLastSection(True)

        # После этого включаем ручной ресайз
        header.setSectionResizeMode(QHeaderView.Interactive)

        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QTableView.SelectRows)
        self.setSelectionMode(QTableView.SingleSelection)
        self.setShowGrid(False)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setDefaultSectionSize(25)

        # Контекстное меню
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def add_row(self, data: list[str]):
        items = [QStandardItem(str(val)) for val in data]
        for item in items:
            item.setEditable(False)
        self.model_.appendRow(items)

    def get_row_text(self, index: QModelIndex):
        return ", ".join(
            self.model_.item(index.row(), c).text()
            for c in range(self.model_.columnCount())
        )

    def show_context_menu(self, pos):
        index = self.indexAt(pos)
        row_text = self.get_row_text(index)
        if not index.isValid():
            return

        menu = QMenu(self)
        copy_action = menu.addAction("Скопировать текст")
        delete_action = menu.addAction("Удалить")
        action = menu.exec_(self.viewport().mapToGlobal(pos))

        if action == copy_action:
            QApplication.clipboard().setText(row_text)

        elif action == delete_action:
            self.remove.emit(row_text)
            self.model_.removeRow(index.row())

    def mouseReleaseEvent(self, e):
        index = self.indexAt(e.pos())
        if not index.isValid():
            self.clearSelection()
            self.setCurrentIndex(QModelIndex())
        return super().mouseReleaseEvent(e)


class ServersWin(MinMaxDisabledWin):
    title_text = "Подключение к серверу"
    connect_text = "Подкл."
    new_server_text = "Сервер, логин, пароль"
    json_file = os.path.join(Static.app_support, "servers.json")

    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.title_text)
        self.set_modality()
        self.setFixedWidth(400)

        # Загрузка данных
        self.data: list[list[str]] = []
        self.init_data()

        # Layout
        self.central_layout = QVBoxLayout()
        self.central_layout.setContentsMargins(5, 5, 5, 5)
        self.central_layout.setSpacing(10)
        self.centralWidget().setLayout(self.central_layout)

        # QLineEdit для нового сервера
        self.new_server = ULineEdit()
        self.new_server.setPlaceholderText(self.new_server_text)
        self.central_layout.addWidget(self.new_server)

        # QListWidget
        self.servers_widget = ServersWidget(self.data)
        self.servers_widget.remove.connect(lambda text: self.remove_server(text))
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
        btn_remove.clicked.connect(lambda: self.remove_btn_cmd())

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
        self.servers_widget.add_row(parts)

        # Добавляем в self.data
        self.data.append(parts)

        # Очищаем QLineEdit
        self.new_server.clear()

        # Сохраняем
        self.save_cmd()

    def remove_btn_cmd(self):
        ind = self.servers_widget.currentIndex()
        if ind.isValid():
            text = self.servers_widget.get_row_text(ind)
            self.servers_widget.model_.removeRow(ind.row())
            self.remove_server(text)

    def remove_server(self, text: str):
        self.data.remove(text.split(", "))
        self.save_cmd()

    def save_cmd(self):
        with open(self.json_file, "w", encoding="utf-8") as file:
            json.dump(self.data, file, indent=4, ensure_ascii=False)

    def connect_cmd(self):
        delay = 0

        for server, login, password in self.data:
            
            if SharedUtils.is_mounted(server):
                continue

            cmd = f"smb://{login}:{password}@{server}"
            QTimer.singleShot(delay, lambda c=cmd: subprocess.run(["open", c]))
            delay += 200  # задержка 200 мс между подключениями

        # Закрыть окно через общее время + небольшой запас
        QTimer.singleShot(delay + 100, self.deleteLater)

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()
        elif a0.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.connect_cmd()
        return super().keyPressEvent(a0)
    