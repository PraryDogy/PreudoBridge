
import subprocess
import webbrowser

import sqlalchemy
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent, QKeyEvent
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton,
                             QVBoxLayout, QWidget)

from cfg import JSON_FILE, LINK, JsonData
from database import STATS, Dbase

from ._base import BaseSlider, OnlyCloseWin

class WinSettings(OnlyCloseWin):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Настройки")
        self.setFixedSize(350, 200)

        main_lay = QVBoxLayout()
        main_lay.setContentsMargins(10, 10, 10, 10)
        main_lay.setSpacing(10)
        self.setLayout(main_lay)

        h_wid = QWidget()
        main_lay.addWidget(h_wid)

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_wid.setLayout(h_lay)

        self.current_size = QLabel("")
        h_lay.addWidget(self.current_size)

        self.clear_btn = QPushButton("Очистить данные")
        self.clear_btn.setFixedWidth(150)
        self.clear_btn.clicked.connect(self.clear_db_cmd)
        h_lay.addWidget(self.clear_btn)
        
        self.slider_values = [2, 5, 10, 100]
        self.slider = BaseSlider(Qt.Horizontal, 0, len(self.slider_values) - 1)
        self.slider.setFixedWidth(100)
        current = JsonData.clear_db
        ind = self.slider_values.index(current)
        self.slider.setValue(ind)
        self.slider.valueChanged.connect(self.update_label)
        main_lay.addWidget(self.slider)

        self.label = QLabel("", self)
        main_lay.addWidget(self.label)
        self.get_current_size()
        self.update_label(ind)

        separator = QFrame()
        separator.setFixedWidth(self.width() - 40)
        separator.setFrameShape(QFrame.HLine)  # Горизонтальный разделитель
        separator.setFrameShadow(QFrame.Sunken)  # Внешний вид (утопленный)
        main_lay.addWidget(separator, alignment=Qt.AlignmentFlag.AlignCenter)

        h_wid = QWidget()
        main_lay.addWidget(h_wid)
        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 15, 0, 15)
        h_wid.setLayout(h_lay)

        open_json_btn = QPushButton("Файл настроек")
        open_json_btn.setFixedWidth(150)
        open_json_btn.clicked.connect(lambda: subprocess.call(["open", JSON_FILE]))
        h_lay.addWidget(open_json_btn)

        open_json_btn = QPushButton("Обновления")
        open_json_btn.setFixedWidth(150)
        open_json_btn.clicked.connect(lambda: webbrowser.open(LINK))
        h_lay.addWidget(open_json_btn)

        main_lay.addStretch()

    def update_label(self, index):
        value = self.slider_values[index]

        if value == 100:
            t = "Максимальный размер данных: без лимита"
        else:
            t = f"Максимальный размер данных: {value}гб"

        self.label.setText(t)
        JsonData.clear_db = value

    def get_current_size(self):
        with Dbase.engine.connect() as conn:
            q = sqlalchemy.select(STATS.c.size).where(STATS.c.name == "main")
            res = conn.execute(q).scalar() or 0

        res = int(res / (1024))
        t = f"Данные: {res}кб"

        if res > 1024:
            res = round(res / (1024), 2)
            t = f"Данные: {res}мб"

        if res > 1024:
            res = round(res / (1024), 2)
            t = f"Данные: {res}гб"

        self.current_size.setText(t)

    def clear_db_cmd(self):
        if Dbase.clear_db():
            self.get_current_size()

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        JsonData.write_config()
    
    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()