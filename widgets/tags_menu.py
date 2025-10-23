from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import (QAction, QListWidget, QListWidgetItem,
                             QVBoxLayout, QWidget)

from cfg import Dynamic, Static

from ._base_widgets import ULineEdit, UMenu


class UItem(QListWidgetItem):
    def __init__(self):
        super().__init__()
        self.rating: int


class UULineEdit(ULineEdit):
    key_press = pyqtSignal()

    def __init__(self):
        super().__init__()

    def keyPressEvent(self, a0):
        if a0.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.key_press.emit()
            self.clearFocus()
        return super().keyPressEvent(a0)


class FiltersMenu(QWidget):
    filter_thumbs = pyqtSignal()
    rearrange_thumbs = pyqtSignal()
    enable_text = "Включить"
    height_ = 155
    item_width = 25
    filter_placeholder = "Фильтр 1, фильтр 2, ..."

    def __init__(self):
        super().__init__()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 10)
        self.layout.setSpacing(5)

        # Список
        self.list = QListWidget()
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setFixedHeight(FiltersMenu.height_)
        item_size = QSize(self.list.width(), FiltersMenu.item_width)

        zero_item = UItem()
        zero_item.rating = 0
        zero_item.setText(Static.LINE_LONG_SYM)
        zero_item.setSizeHint(item_size)
        self.list.addItem(zero_item)

        for i in range(1, 6):
            item = UItem()
            item.rating = i
            item.setText(Static.STAR_SYM * i)
            item.setSizeHint(item_size)
            self.list.addItem(item)

        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.show_context_menu)
        self.list.itemClicked.connect(self.handle_item_click)

        # QLineEdit под списком
        self.line_edit = UULineEdit()
        self.line_edit.setPlaceholderText(self.filter_placeholder)
        self.line_edit.textChanged.connect(self.on_text_changed)
        self.line_edit.key_press.connect(
            lambda: (self.filter_thumbs.emit(), self.rearrange_thumbs.emit())
        )

        # Добавляем виджеты в layout
        self.layout.addWidget(self.list)
        self.layout.addWidget(self.line_edit)

    def on_text_changed(self, text: str):
        self.line_edit.move_clear_btn()
        if text:
            self.line_edit.clear_btn.show()
            Dynamic.word_filters = [i.strip() for i in self.line_edit.text().split(",")]
        else:
            self.line_edit.clear_btn.hide()
            Dynamic.word_filters.clear()
            self.filter_thumbs.emit()
            self.rearrange_thumbs.emit()
            self.line_edit.clearFocus()

    # Контекстное меню
    def show_context_menu(self, position):
        item: UItem = self.list.itemAt(position)
        if not item:
            return
        menu = UMenu(parent=self)
        enable_action = QAction(FiltersMenu.enable_text, menu)
        if Dynamic.rating_filter == item.rating:
            enable_action.setDisabled(True)
        enable_action.triggered.connect(lambda: self.item_cmd(item.rating))
        menu.addAction(enable_action)
        menu.show_under_cursor()

    # Клик по элементу
    def handle_item_click(self, item: 'UItem'):
        self.item_cmd(item.rating)

    # Обновление фильтра
    def item_cmd(self, rating: int):
        Dynamic.rating_filter = rating
        self.filter_thumbs.emit()
        self.rearrange_thumbs.emit()

    def reset(self):
        Dynamic.rating_filter = 0
        self.list.setCurrentRow(0)
