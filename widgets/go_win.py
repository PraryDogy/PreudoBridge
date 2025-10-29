from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from ._base_widgets import MinMaxDisabledWin, ULineEdit


class GoToWin(MinMaxDisabledWin):
    closed = pyqtSignal(tuple)
    placeholder_text = "Вставьте путь к файлу/папке"
    title_text = "Перейти к ..."
    input_width = 270
    finder = "Finder"
    go_to_text = "Перейти"

    def __init__(self):
        """
        Окно перейти:
        - поле ввода
        - кнопка "Перейти" - переход к директории внутри приложения, отобразится
        новая сетка с указанным путем
        - кнопка "Finder" - путь откроется в Finder
        """
        super().__init__()
        self.set_modality()
        self.setWindowTitle(GoToWin.title_text)
        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 10, 10, 5)
        v_lay.setSpacing(5)
        self.centralWidget().setLayout(v_lay)

        self.input_wid = ULineEdit()
        self.input_wid.textChanged.connect(self.text_changed)
        self.input_wid.setPlaceholderText(GoToWin.placeholder_text)
        self.input_wid.setFixedWidth(GoToWin.input_width)

        v_lay.addWidget(self.input_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        h_wid = QWidget()
        v_lay.addWidget(h_wid)

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)
        h_wid.setLayout(h_lay)

        h_lay.addStretch()

        go_btn = QPushButton(GoToWin.go_to_text)
        go_btn.setFixedWidth(100)
        go_btn.clicked.connect(self.inner_clicked)
        h_lay.addWidget(go_btn)

        go_finder_btn = QPushButton(GoToWin.finder)
        go_finder_btn.setFixedWidth(100)
        go_finder_btn.clicked.connect(self.finder_clicked)
        h_lay.addWidget(go_finder_btn)

        h_lay.addStretch()
        self.adjustSize()
        self.input_wid.move_clear_btn()

    def text_changed(self, text: str):
        if text:
            self.input_wid.clear_btn.show()
        else:
            self.input_wid.clear_btn.hide()

    def inner_clicked(self):
        data = 0, self.input_wid.text()
        self.closed.emit(data)
        self.deleteLater()

    def finder_clicked(self):
        data = 1, self.input_wid.text()
        self.closed.emit(data)
        self.deleteLater()

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        is_ok_pressed = a0.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)

        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()

        elif a0.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if is_ok_pressed:
                self.finder_clicked()

        elif is_ok_pressed:
            self.inner_clicked()