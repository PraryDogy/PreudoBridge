from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QTabWidget

from cfg import Dynamic

from ._base_widgets import SmallBtn, UTextEdit


class MenuFilters(QTabWidget):
    filter_thumbs = pyqtSignal()
    rearrange_thumbs = pyqtSignal()
    enable_text = "Включить"
    height_ = 155
    item_width = 25
    filter_placeholder = "Фильтр 1, фильтр 2, ..."

    def __init__(self):
        super().__init__()

        # layout_ = QVBoxLayout(self)
        # layout_.setContentsMargins(0, 0, 0, 5)
        # layout_.setSpacing(5)

        wid = QWidget()
        self.addTab(wid, "Фильтры")
        self.tabBar().hide()

        layout_ = QVBoxLayout()
        layout_.setContentsMargins(0, 0, 0, 0)
        layout_.setSpacing(5)
        wid.setLayout(layout_)

        self.line_edit = UTextEdit()
        self.line_edit.setPlaceholderText(self.filter_placeholder)
        self.line_edit.textChanged.connect(self.on_text_changed)
        layout_.addWidget(self.line_edit)

        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 3)
        btn_layout.setSpacing(10)
        self.apply_btn = SmallBtn("Применить")
        self.apply_btn.setFixedWidth(95)
        self.clear_btn = SmallBtn("Очистить")
        self.clear_btn.setFixedWidth(95)
        self.apply_btn.clicked.connect(
            lambda: (
                self.line_edit.clearFocus(),
                self.filter_thumbs.emit(),
                self.rearrange_thumbs.emit()
            )
        )
        self.clear_btn.clicked.connect(self.clear_btn_cmd)
        btn_layout.addStretch()
        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        layout_.addLayout(btn_layout)

    def clear_btn_cmd(self):
        self.line_edit.clear()
        self.line_edit.clearFocus()

    def on_text_changed(self):
        text = self.line_edit.toPlainText()
        if text:
            Dynamic.word_filters = [i.strip() for i in text.split(",") if i]
            if text[-1] == ",":
                self.filter_thumbs.emit()
                self.rearrange_thumbs.emit()
        elif text == "":
            Dynamic.word_filters.clear()
            self.filter_thumbs.emit()
            self.rearrange_thumbs.emit()
