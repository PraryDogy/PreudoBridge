
import sqlalchemy
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCloseEvent, QKeyEvent, QPixmap
from PyQt5.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
                             QPushButton, QVBoxLayout, QWidget)

from cfg import Config, JsonData
from database import STATS, Dbase, Engine
from signals import SIGNALS

from ._base import BaseSlider


class NameLabelHidden(QWidget):
    def __init__(self):
        super().__init__()

        main_layout = QGridLayout()
        self.setLayout(main_layout)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(0)

        svg = "images/ded.jpg"
        colors = "🔴🟠🟡🟢"
        stars = "★★★★★"
        filename = "ded.jpg"

        simple_view = QWidget()
        simple_view.setObjectName("sett_thumb")
        simple_view.setStyleSheet("#sett_thumb { border: 1px solid transparent; }")
        simple_view.mouseReleaseEvent = lambda e, b=True: self.select_widget(simple_view, b)
        main_layout.addWidget(simple_view, 0 , 0)

        simple_view_lay = QVBoxLayout()
        simple_view.setLayout(simple_view_lay)

        image_label = QLabel()
        image_label.setPixmap(QPixmap(svg))
        simple_view_lay.addWidget(image_label, alignment=Qt.AlignmentFlag.AlignTop)

        info_view = QWidget()
        info_view.setObjectName("sett_thumb")
        info_view.setStyleSheet("#sett_thumb { border: 1px solid transparent; }")
        info_view.mouseReleaseEvent = lambda e, b=False: self.select_widget(info_view, b)
        main_layout.addWidget(info_view, 0 , 1)

        info_view_lay = QVBoxLayout()
        info_view.setLayout(info_view_lay)

        image_label = QLabel()
        image_label.setPixmap(QPixmap(svg))
        info_view_lay.addWidget(image_label, alignment=Qt.AlignmentFlag.AlignTop)

        text_label = QLabel(text=f"{colors}\n{stars}\n{filename}")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_view_lay.addWidget(text_label, alignment=Qt.AlignmentFlag.AlignBottom)
        info_view.setObjectName("sett_thumb")

        if JsonData.name_label_hidden == 1:
            self.set_white(simple_view)
        else:
            self.set_white(info_view)

    def set_transparent(self, wid: QWidget):
        wid.setStyleSheet("#sett_thumb { border: 1px solid transparent; }")

    def set_white(self, wid: QWidget):
        wid.setStyleSheet("#sett_thumb { border: 1px solid white; }")

    def select_widget(self, wid: QWidget, b: bool):
        self.deselect_widgets()
        self.set_white(wid)
        JsonData.name_label_hidden = b
        Config.write_config()
        SIGNALS.resize_grid.emit(None)

    def deselect_widgets(self):
        for i in self.findChildren(QWidget):
            self.set_transparent(i)


class WinSettings(QWidget):
    def __init__(self):
        super().__init__()
        
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Настройки")
        self.setFixedSize(350, 400)

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
        separator.setFrameShape(QFrame.HLine)  # Горизонтальный разделитель
        separator.setFrameShadow(QFrame.Sunken)  # Внешний вид (утопленный)
        main_lay.addWidget(separator)

        thumb_type_title = QLabel("Вид")
        main_lay.addWidget(thumb_type_title)

        self.name_label_hidden = NameLabelHidden()
        main_lay.addWidget(self.name_label_hidden)

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
        with Engine.engine.connect() as conn:
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
        Config.write_config()
    
    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()