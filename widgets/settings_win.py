import subprocess
from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QCheckBox, QFrame, QGroupBox, QHBoxLayout, QLabel,
                             QPushButton, QVBoxLayout, QWidget)

from cfg import JsonData, Static

from ._base_widgets import MinMaxDisabledWin, USvgSqareWidget

LEFT_W = 110


class ClearData(QGroupBox):
    clear_data_clicked = pyqtSignal()
    clear_text = "Очистить"
    descr_text = "Очистить данные в этой папке"

    def __init__(self):
        super().__init__()

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        self.setLayout(h_lay)

        btn_ = QPushButton(ClearData.clear_text)
        btn_.clicked.connect(self.clear_data_clicked.emit)
        btn_.setFixedWidth(LEFT_W)
        h_lay.addWidget(btn_)

        descr = QLabel(ClearData.descr_text)
        h_lay.addWidget(descr)


class JsonFile(QGroupBox):
    json_text = "Json"
    json_descr_text = "Открыть текстовый файл настроек"

    def __init__(self):
        super().__init__()

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        self.setLayout(h_lay)

        btn_ = QPushButton(JsonFile.json_text)
        btn_.setFixedWidth(LEFT_W)
        btn_.clicked.connect(
            lambda: subprocess.call(["open", Static.JSON_FILE])
        )
        h_lay.addWidget(btn_)

        descr = QLabel(JsonFile.json_descr_text)
        h_lay.addWidget(descr)


class About(QGroupBox):
    svg_size = 70
    text_ = "\n".join(
        [
            f"{Static.APP_NAME} {Static.APP_VER}",
            f"{datetime.now().year} Evgeny Loshakev"
        ]
    )

    def __init__(self):
        super().__init__()

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        self.setLayout(h_lay)

        svg_ = USvgSqareWidget(Static.APP_ICON_SVG, About.svg_size)
        h_lay.addWidget(svg_)

        descr = QLabel(About.text_)
        h_lay.addWidget(descr)


class CheckboxGroup(QGroupBox):
    load_st_grid = pyqtSignal()
    show_texts_sig = pyqtSignal()
    text_ = "Отобазить скрытые файлы"
    go_to_text = "\n".join([
    "Включить автоматический переход при нажатии \"Перейти\",",
    " если путь скопирован в буфер обмена.",
    ])
    show_texts_text = "Показывать подписи к кнопкам"
    left_margin = 7

    def __init__(self):
        super().__init__()

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(self.left_margin, 0, 0, 0)
        self.setLayout(v_lay)

        self.show_hidden = QCheckBox(" " + self.text_)
        v_lay.addWidget(self.show_hidden)

        self.enable_go_to = QCheckBox(" " + self.go_to_text)
        v_lay.addWidget(self.enable_go_to)

        self.show_texts = QCheckBox(" " + self.show_texts_text)
        v_lay.addWidget(self.show_texts)

        if JsonData.show_hidden:
            self.show_hidden.setChecked(True)

        if JsonData.go_to_now:
            self.enable_go_to.setChecked(True)

        if JsonData.show_text:
            self.show_texts.setChecked(True)

        self.show_hidden.stateChanged.connect(self.on_state_changed)
        self.enable_go_to.stateChanged.connect(self.on_state_changed_two)
        self.show_texts.stateChanged.connect(self.show_texts_cmd)
        
    def on_state_changed(self, value: int):
        data = {0: False, 2: True}
        JsonData.show_hidden = data.get(value)
        self.load_st_grid.emit()
 
    def on_state_changed_two(self, value: int):
        data = {0: False, 2: True}
        JsonData.go_to_now = data.get(value)

    def show_texts_cmd(self):
        if JsonData.show_text:
            JsonData.show_text = False
            self.show_texts.setChecked(False)
        else:
            JsonData.show_text = True
            self.show_texts.setChecked(True)

        self.show_texts_sig.emit()


class SvgFrame(QFrame):
    clicked = pyqtSignal()

    def __init__(self, svg_path: str, label_text: str):
        super().__init__()
        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(0, 0, 0, 0)
        v_lay.setSpacing(0)
        self.setLayout(v_lay)

        self.svg_container = QFrame()
        self.svg_container.setObjectName("svg_container")
        self.svg_container.setStyleSheet(self.regular_style())
        v_lay.addWidget(self.svg_container)

        svg_lay = QVBoxLayout()
        svg_lay.setContentsMargins(0, 0, 0, 0)
        svg_lay.setSpacing(0)
        self.svg_container.setLayout(svg_lay)

        self.svg_widget = QSvgWidget(svg_path)
        self.svg_widget.setFixedSize(50, 50)
        svg_lay.addWidget(self.svg_widget)

        label = QLabel(label_text)
        label.setAlignment(Qt.AlignCenter)
        v_lay.addWidget(label)

    def regular_style(self):
        return """
            #svg_container {
                border: 2px solid transparent;
                border-radius: 10px;
            }
        """

    def border_style(self):
        return """
            #svg_container {
                border: 2px solid #007aff;
                border-radius: 10px;
            }
        """

    def selected(self, enable=True):
        if enable:
            self.svg_container.setStyleSheet(
                self.border_style()
            )
        else:
            self.svg_container.setStyleSheet(
                self.regular_style()
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()


class Themes(QGroupBox):
    system_text = "Авто"
    dark_text = "Темная"
    light_text = "Светлая"
    theme_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(10, 10, 10, 10)
        h_lay.setSpacing(20)
        h_lay.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.setLayout(h_lay)

        self.frames = []

        self.system_theme = SvgFrame(Static.SYSTEM_THEME_SVG, self.system_text)
        self.dark_theme = SvgFrame(Static.DARK_THEME_SVG, self.dark_text)
        self.light_theme = SvgFrame(Static.LIGHT_THEME_SVG, self.light_text)

        for f in (self.system_theme, self.dark_theme, self.light_theme):
            h_lay.addWidget(f)
            self.frames.append(f)
            f.clicked.connect(self.on_frame_clicked)

        if JsonData.dark_mode is None:
            self.set_selected(self.system_theme)
        elif JsonData.dark_mode:
            self.set_selected(self.dark_theme)
        else:
            self.set_selected(self.light_theme)

    def on_frame_clicked(self):
        sender: SvgFrame = self.sender()
        self.set_selected(sender)

        if sender == self.system_theme:
            JsonData.dark_mode = None
        elif sender == self.dark_theme:
            JsonData.dark_mode = True
        elif sender == self.light_theme:
            JsonData.dark_mode = False

        self.theme_changed.emit()

    def set_selected(self, selected_frame: SvgFrame):
        for f in self.frames:
            f.selected(f is selected_frame)


class SettingsWin(MinMaxDisabledWin):
    remove_db = pyqtSignal()
    load_st_grid = pyqtSignal()
    title_text = "Настройки"
    theme_changed = pyqtSignal()
    hh = 460
    show_texts_sig = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle(SettingsWin.title_text)
        self.set_modality()
        self.setFixedHeight(SettingsWin.hh)

        main_lay = QVBoxLayout()
        main_lay.setContentsMargins(10, 0, 10, 10)
        main_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(main_lay)

        h_wid = QWidget()
        main_lay.addWidget(h_wid)

        checkbox_group = CheckboxGroup()
        checkbox_group.load_st_grid.connect(self.load_st_grid.emit)
        checkbox_group.show_texts_sig.connect(self.show_texts_sig.emit)
        main_lay.addWidget(checkbox_group)

        themes_wid = Themes()
        themes_wid.theme_changed.connect(self.theme_changed_cmd)
        main_lay.addWidget(themes_wid)

        clear_data_wid = ClearData()
        clear_data_wid.clear_data_clicked.connect(self.remove_db.emit)
        main_lay.addWidget(clear_data_wid)

        json_wid = JsonFile()
        main_lay.addWidget(json_wid)

        about_wid = About()
        main_lay.addWidget(about_wid)

        self.adjustSize()
        self.setFixedSize(self.width() + 30, self.height())

    def theme_changed_cmd(self):
        self.theme_changed.emit()
        self.adjustSize()
    
    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()

    def deleteLater(self):
        JsonData.write_config()
        super().deleteLater()