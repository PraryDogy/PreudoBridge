import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent, QKeyEvent
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QAction, QHBoxLayout, QLabel, QMenu, QMenuBar,
                             QSpacerItem, QVBoxLayout, QWidget)

from cfg import Static
from system.utils import Utils

from ._base_widgets import MinMaxDisabledWin, UMenu
from .servers_win import ServersWin
from .settings_win import SettingsWin


class SelectableLabel(QLabel):
    """
    QLabel с возможностью выделения текста и кастомным контекстным меню для копирования.

    Особенности:
        - Текст можно выделять мышью.
        - Контекстное меню позволяет копировать выделенный текст или весь текст.
    """

    INFO_TEXT = "\n".join([
        f"Version {Static.app_ver}",
        "Developed by Evlosh",
        "email: evlosh@gmail.com",
        "telegram: evlosh",
    ])
    copy_text = "Копировать"
    copy_all_text = "Копировать все"

    def __init__(self, parent: QWidget):
        super().__init__(parent)

        # --- Текст информации ---
        self.setText(self.INFO_TEXT)

        # --- Настройка взаимодействия с текстом ---
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.setCursor(Qt.CursorShape.IBeamCursor)

    def contextMenuEvent(self, ev: QContextMenuEvent | None) -> None:
        """Создаёт кастомное контекстное меню для копирования текста."""
        context_menu = UMenu(ev)

        # --- Копировать выделенный текст ---
        copy_text = QAction(parent=context_menu, text=self.copy_text)
        copy_text.triggered.connect(
            lambda: Utils.copy_text(self.selectedText())
        )
        context_menu.addAction(copy_text)

        context_menu.addSeparator()

        # --- Копировать весь текст ---
        select_all = QAction(parent=context_menu, text=self.copy_all_text)
        select_all.triggered.connect(
            lambda: Utils.copy_text(self.text())
        )
        context_menu.addAction(select_all)

        # --- Показать контекстное меню ---
        context_menu.show_umenu()


class AboutWin(MinMaxDisabledWin):
    """
    Окно "О программе" с информацией о версии, авторе и контактами.
    
    Особенности:
        - Отображает иконку приложения.
        - Содержит SelectableLabel с информацией, которую можно копировать.
        - Закрывается по Escape или Enter.
    """
    ww, hh = 280, 240
    svg_ww, svg_hh = 150, 130
    svg_icon = os.path.join(Static.icons_rel_dir, "icon.svg")

    def __init__(self):
        super().__init__()

        # --- Настройка окна ---
        self.setWindowTitle(Static.app_name)

        self.central_layout = QVBoxLayout()
        self.central_layout.setContentsMargins(10, 0, 10, 10)
        self.central_layout.setSpacing(0)
        self.centralWidget().setLayout(self.central_layout)

        # --- Иконка приложения ---
        icon = QSvgWidget()
        icon.load(self.svg_icon)
        icon.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        icon.setFixedSize(self.svg_ww, self.svg_hh)
        self.central_layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignCenter)

        # --- Информационный текст ---
        lbl = SelectableLabel(self)
        self.central_layout.addWidget(lbl)

        self.adjustSize()
        self.setFixedWidth(self.ww)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        """Закрывает окно по Escape или Enter."""
        if a0.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return):
            self.deleteLater()


class BarMacos(QMenuBar):
    """
    Меню-бар для macOS с основными пунктами:
        - Открыть настройки
        - О приложении

    Атрибуты:
        settings_win: экземпляр окна настроек (WinSettings)
        about_win: экземпляр окна "О программе" (AboutWin)
    """
    
    menu_text = "Меню"
    about_text = "Об авторе"
    settings_text = "Настройки"
    servers_text = "Подключение (Cmd + K)"
    new_win_text = "Новое окно (Cmd + N)"
    go_to_text = "Перейти к директории"
    new_win = pyqtSignal()
    servers_win = pyqtSignal()
    settings_win = pyqtSignal()
    go_to_win = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.mainMenu = QMenu(self.menu_text, self)

        actionServer = QAction(self.servers_text, self)
        actionServer.triggered.connect(self.servers_win.emit)
        self.mainMenu.addAction(actionServer)

        actionNewWin = QAction(self.new_win_text, self)
        actionNewWin.triggered.connect(self.new_win.emit)
        self.mainMenu.addAction(actionNewWin)

        actionGoTo = QAction(self.go_to_text, self)
        actionGoTo.triggered.connect(self.go_to_win.emit)
        self.mainMenu.addAction(actionGoTo)

        actionSettings = QAction(self.settings_text, self)
        actionSettings.triggered.connect(self.settings_win.emit)
        self.mainMenu.addAction(actionSettings)

        self.mainMenu.addSeparator()

        # --- Пункт "О приложении" ---
        actionAbout = QAction(self.about_text, self)
        actionAbout.triggered.connect(self.open_about_window)
        self.mainMenu.addAction(actionAbout)

        # --- Добавляем меню в меню-бар ---
        self.addMenu(self.mainMenu)
        self.setNativeMenuBar(True)

    def open_about_window(self):
        """Открывает окно 'О программе'."""
        self.about_win = AboutWin()
        self.about_win.center(self.window())
        self.about_win.show()
