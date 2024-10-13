import sys

from PyQt5.QtGui import QCloseEvent
import sqlalchemy
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QLabel, QHBoxLayout, QSlider,
                             QVBoxLayout, QWidget, QPushButton)

from cfg import Config
from database import Dbase, Stats


class SliderWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Настройки")
        self.setGeometry(100, 100, 300, 150)

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 10, 10, 10)
        v_lay.setSpacing(10)
        self.setLayout(v_lay)

        h_wid = QWidget()
        v_lay.addWidget(h_wid)

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_wid.setLayout(h_lay)

        self.current_size = QLabel("")
        h_lay.addWidget(self.current_size)

        self.clear_btn = QPushButton("Очистить данные")
        h_lay.addWidget(self.clear_btn)
        
        self.slider_values = [2, 5, 10, 100]
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(len(self.slider_values) - 1)
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.setTickInterval(1)
        v_lay.addWidget(self.slider)

        self.label = QLabel("", self)
        v_lay.addWidget(self.label)
        self.get_current_size()

        v_lay.addStretch(0)

        self.slider.valueChanged.connect(self.update_label)
        current = Config.json_data.get("clear_db")
        self.slider.setValue(self.slider_values.index(current))

    def update_label(self, index):
        value = self.slider_values[index]

        if value == 100:
            t = "Без лимита"
        else:
            t = f"Максимальный размер данных: {value}гб"

        self.label.setText(t)
        Config.json_data["clear_db"] = value

    def get_current_size(self):
        sess = Dbase.get_session()
        q = sqlalchemy.select(Stats.size).where(Stats.name=="main")
        res = sess.execute(q).first()[0]

        res = round(res / (1024**2), 2)
        t = f"Данные: {res}мб"

        if res > 1000:
            res = round(res / 1024, 2)
            t = f"Данные: {res}гб"

        self.current_size.setText(t)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        Config.write_json_data()
        return super().closeEvent(a0)

Dbase.init_db()
app = QApplication(sys.argv)
window = SliderWindow()
window.show()
sys.exit(app.exec_())