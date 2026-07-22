import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QContextMenuEvent, QKeyEvent, QPixmap
from PyQt6.QtWidgets import QLabel, QMenu, QMenuBar, QVBoxLayout, QWidget

from cfg import Static
from system.utils import Utils

from ._base_widgets import UMainWidget, UMenu


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


class AboutWin(UMainWidget):
    ww, hh = 280, 240
    icon_size = 150
    icon_path = os.path.join(Static.internal_images_dir, "icon.png")

    def __init__(self):
        super().__init__()
        self.set_always_on_top()
        self.set_close_only()
        self.setWindowTitle(Static.app_name)

        self.central_layout.setContentsMargins(10, 0, 10, 10)
        self.central_layout.setSpacing(0)

        icon = QLabel()
        pixmap = QPixmap(self.icon_path)
        pixmap = Utils.qiconed_resize(pixmap, self.icon_size)
        icon.setPixmap(pixmap)
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
    servers_text = "Подключение (⌘ + K)"
    new_win_text = "Новое окно (⌘ + N)"
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
