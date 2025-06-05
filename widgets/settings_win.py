import os
import shutil
import subprocess
from datetime import datetime

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QKeyEvent, QPalette
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QApplication, QCheckBox, QFrame, QGroupBox,
                             QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                             QWidget)

from cfg import JsonData, Static
from paletes import UPallete

from ._base_items import (MinMaxDisabledWin, URunnable, USvgSqareWidget,
                          UThreadPool)

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


class WorkerSignals(QObject):
    finished_ = pyqtSignal(bool)


class DownloadUpdate(URunnable):
    def __init__(self):
        super().__init__()
        self.signals_ = WorkerSignals()

    def task(self):
        for i in JsonData.udpdate_file_paths:
            if os.path.exists(i):

                dest = shutil.copy2(
                    src=i,
                    dst=os.path.expanduser("~/Downloads")
                )
                subprocess.run(["open", "-R", dest])
                self.signals_.finished_.emit(True)
                return

        self.signals_.finished_.emit(False)


class Updates(QGroupBox):
    wait_text = "Подождите"
    error_text = "Ошибка"
    no_connection_text = "Нет подключения к диску"
    download_text = "Скачать обновления"
    updates_text = "Обновления"
    timer_ms = 1500

    def __init__(self):
        super().__init__()

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        self.setLayout(h_lay)

        self.btn_ = QPushButton(Updates.updates_text)
        self.btn_.setFixedWidth(LEFT_W)
        self.btn_.clicked.connect(self.update_cmd)

        h_lay.addWidget(self.btn_)

        self.descr = QLabel(Updates.download_text)
        h_lay.addWidget(self.descr)

    def update_cmd(self, *args):
        self.btn_.setText(Updates.wait_text)
        self.task_ = DownloadUpdate()
        self.task_.signals_.finished_.connect(self.update_cmd_fin)
        UThreadPool.start(self.task_)

    def update_cmd_fin(self, arg: bool):
        if arg:
            self.btn_.setText(Updates.updates_text)
        else:
            self.btn_.setText(Updates.error_text)
            self.descr.setText(Updates.no_connection_text)
            QTimer.singleShot(Updates.timer_ms, lambda: self.btn_.setText(Updates.updates_text))
            QTimer.singleShot(Updates.timer_ms, lambda: self.descr.setText(Updates.download_text))


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

        svg_ = USvgSqareWidget(Static.ICON_SVG, About.svg_size)
        h_lay.addWidget(svg_)

        descr = QLabel(About.text_)
        h_lay.addWidget(descr)


class CheckboxGroup(QGroupBox):
    load_st_grid = pyqtSignal()
    text_ = "Отобазить скрытые файлы"
    go_to_text = "\n".join([
    "Включить автоматический переход при нажатии \"Перейти\",",
    " если путь скопирован в буфер обмена.",
    ])
    left_margin = 7

    def __init__(self):
        super().__init__()

        h_lay = QVBoxLayout()
        h_lay.setContentsMargins(CheckboxGroup.left_margin, 0, 0, 0)
        self.setLayout(h_lay)

        self.checkbox = QCheckBox(" " + CheckboxGroup.text_)
        h_lay.addWidget(self.checkbox)

        if JsonData.show_hidden:
            self.checkbox.setChecked(True)
        
        self.checkbox.stateChanged.connect(self.on_state_changed)

        self.checkbox_two = QCheckBox(" " + CheckboxGroup.go_to_text)
        h_lay.addWidget(self.checkbox_two)

        if JsonData.go_to_now:
            self.checkbox_two.setChecked(True)
        
        self.checkbox_two.stateChanged.connect(self.on_state_changed_two)
        
    def on_state_changed(self, value: int):
        data = {0: False, 2: True}
        JsonData.show_hidden = data.get(value)
        self.load_st_grid.emit()
 
    def on_state_changed_two(self, value: int):
        data = {0: False, 2: True}
        JsonData.go_to_now = data.get(value)


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

    def __init__(self):
        super().__init__()
        self.setWindowTitle(SettingsWin.title_text)
        self.set_modality()

        main_lay = QVBoxLayout()
        main_lay.setContentsMargins(10, 0, 10, 10)
        main_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(main_lay)

        h_wid = QWidget()
        main_lay.addWidget(h_wid)

        show_hidden = CheckboxGroup()
        show_hidden.load_st_grid.connect(self.load_st_grid.emit)
        main_lay.addWidget(show_hidden)

        themes_wid = Themes()
        themes_wid.theme_changed.connect(self.theme_changed.emit)
        main_lay.addWidget(themes_wid)

        clear_data_wid = ClearData()
        clear_data_wid.clear_data_clicked.connect(self.remove_db.emit)
        main_lay.addWidget(clear_data_wid)

        json_wid = JsonFile()
        main_lay.addWidget(json_wid)

        updates_wid = Updates()
        main_lay.addWidget(updates_wid)

        about_wid = About()
        main_lay.addWidget(about_wid)

        self.adjustSize()
        self.setFixedSize(self.width() + 30, self.height())
    
    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()

    def deleteLater(self):
        JsonData.write_config()
        super().deleteLater()