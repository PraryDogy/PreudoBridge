import os
import shutil
import subprocess
from datetime import datetime

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QCheckBox, QGroupBox, QHBoxLayout, QLabel,
                             QPushButton, QVBoxLayout, QWidget)

from cfg import JsonData, Static

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
        UThreadPool.start(runnable=self.task_)

    def update_cmd_fin(self, arg: bool):
        if arg:
            self.btn_.setText(Updates.updates_text)
        else:
            self.btn_.setText(Updates.error_text)
            self.descr.setText(Updates.no_connection_text)
            QTimer.singleShot(1500, lambda: self.btn_.setText(Updates.updates_text))
            QTimer.singleShot(1500, lambda: self.descr.setText(Updates.download_text))


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


class ShowHidden(QGroupBox):
    load_st_grid = pyqtSignal()
    text_ = "Отобазить скрытые файлы"

    def __init__(self):
        super().__init__()

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(7, 0, 0, 0)
        self.setLayout(h_lay)

        self.checkbox = QCheckBox(" " + ShowHidden.text_)
        h_lay.addWidget(self.checkbox)

        if JsonData.show_hidden:
            self.checkbox.setChecked(True)
        
        self.checkbox.stateChanged.connect(self.on_state_changed)
        
    def on_state_changed(self, value: int):
        data = {0: False, 2: True}
        JsonData.show_hidden = data.get(value)
        self.load_st_grid.emit()


class SettingsWin(MinMaxDisabledWin):
    remove_db = pyqtSignal()
    load_st_grid = pyqtSignal()
    title_text = "Настройки"

    def __init__(self):
        super().__init__()
        self.setWindowTitle(SettingsWin.title_text)
        self.set_modality()

        main_lay = QVBoxLayout()
        main_lay.setContentsMargins(10, 0, 10, 15)
        self.setLayout(main_lay)

        h_wid = QWidget()
        main_lay.addWidget(h_wid)

        show_hidden = ShowHidden()
        show_hidden.load_st_grid.connect(self.load_st_grid.emit)
        main_lay.addWidget(show_hidden)

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