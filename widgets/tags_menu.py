from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtWidgets import (QAction, QHBoxLayout, QListWidget,
                             QListWidgetItem, QPushButton, QTabWidget,
                             QVBoxLayout, QWidget)

from cfg import Dynamic, Static

from ._base_widgets import UMenu, UTextEdit


class UItem(QListWidgetItem):
    def __init__(self):
        super().__init__()
        self.rating: int


class FiltersMenu(QWidget):
    filter_thumbs = pyqtSignal()
    rearrange_thumbs = pyqtSignal()
    enable_text = "Включить"
    height_ = 155
    item_width = 25
    filter_placeholder = "Фильтр 1, фильтр 2, ..."

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 5)
        layout.setSpacing(5)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # --- вкладка 1: список ---
        self.tab_list = QWidget()
        tab1_layout = QVBoxLayout(self.tab_list)
        tab1_layout.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setFixedHeight(self.height_)
        item_size = QSize(self.list.width(), self.item_width)

        zero_item = UItem()
        zero_item.rating = 0
        zero_item.setText(Static.long_line_symbol)
        zero_item.setSizeHint(item_size)
        self.list.addItem(zero_item)

        for i in range(1, 6):
            item = UItem()
            item.rating = i
            item.setText(Static.star_symbol * i)
            item.setSizeHint(item_size)
            self.list.addItem(item)

        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.show_context_menu)
        self.list.itemClicked.connect(self.handle_item_click)
        tab1_layout.addWidget(self.list)
        self.tabs.addTab(self.tab_list, "Рейтинг")

        # --- вкладка 2: фильтр текста ---
        self.tab_filter = QWidget()
        tab2_layout = QVBoxLayout(self.tab_filter)
        tab2_layout.setSpacing(5)
        tab2_layout.setContentsMargins(0, 0, 0, 0)
        self.line_edit = UTextEdit()
        self.line_edit.setPlaceholderText(self.filter_placeholder)
        self.line_edit.textChanged.connect(self.on_text_changed)
        tab2_layout.addWidget(self.line_edit)

        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(10)
        self.apply_btn = QPushButton("Применить")
        self.apply_btn.setFixedWidth(95)
        self.clear_btn = QPushButton("Очистить")
        self.clear_btn.setFixedWidth(95)
        self.apply_btn.clicked.connect(
            lambda: (
                self.line_edit.clearFocus(),
                self.filter_thumbs.emit(),
                self.rearrange_thumbs.emit()
            )
        )
        self.clear_btn.clicked.connect(
            lambda: (
                self.line_edit.clear(),
                self.line_edit.clearFocus(),
                self.filter_thumbs.emit(),
                self.rearrange_thumbs.emit(),
            )
        )
        btn_layout.addStretch()
        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        tab2_layout.addLayout(btn_layout)

        self.tabs.addTab(self.tab_filter, "Фильтры")

    def on_text_changed(self):
        text = self.line_edit.toPlainText()
        if text:
            Dynamic.word_filters = [i.strip() for i in text.split(",")]
        else:
            Dynamic.word_filters.clear()

    def show_context_menu(self, position):
        item: UItem = self.list.itemAt(position)
        if not item:
            return
        menu = UMenu(parent=self)
        enable_action = QAction(self.enable_text, menu)
        if Dynamic.rating_filter == item.rating:
            enable_action.setDisabled(True)
        enable_action.triggered.connect(lambda: self.item_cmd(item.rating))
        menu.addAction(enable_action)
        menu.show_under_cursor()

    def handle_item_click(self, item: 'UItem'):
        self.item_cmd(item.rating)

    def item_cmd(self, rating: int):
        Dynamic.rating_filter = rating
        self.filter_thumbs.emit()
        self.rearrange_thumbs.emit()

    def reset(self):
        Dynamic.rating_filter = 0
        self.list.setCurrentRow(0)
