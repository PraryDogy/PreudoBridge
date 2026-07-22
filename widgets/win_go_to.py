from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ._base_widgets import UMainWindow, ULineEdit, BtnSmall


class WinGoTo(UMainWindow):
    closed = pyqtSignal(str)
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
        self.set_always_on_top()
        self.set_close_only()
        self.setWindowTitle(WinGoTo.title_text)
        v_lay = QVBoxLayout(self.centralWidget())
        v_lay.setContentsMargins(10, 10, 10, 5)
        v_lay.setSpacing(5)

        self.input_wid = ULineEdit()
        self.input_wid.textChanged.connect(self.text_changed)
        self.input_wid.setPlaceholderText(WinGoTo.placeholder_text)
        self.input_wid.setFixedWidth(WinGoTo.input_width)

        v_lay.addWidget(self.input_wid, alignment=Qt.AlignmentFlag.AlignCenter)

        h_wid = QWidget()
        v_lay.addWidget(h_wid)

        h_lay = QHBoxLayout(h_wid)
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_lay.setSpacing(10)

        h_lay.addStretch()

        go_btn = BtnSmall(WinGoTo.go_to_text)
        go_btn.clicked.connect(self.inner_clicked)
        h_lay.addWidget(go_btn)

        h_lay.addStretch()
        self.adjustSize()
        self.input_wid.move_clear_btn()

    def text_changed(self, text: str):
        if text:
            self.input_wid.clear_btn.show()
        else:
            self.input_wid.clear_btn.hide()

    def inner_clicked(self):
        self.closed.emit(self.input_wid.text())
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