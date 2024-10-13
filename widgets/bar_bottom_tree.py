import sqlalchemy
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCloseEvent, QKeyEvent
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QSlider,
                             QVBoxLayout, QWidget)

from cfg import Config
from database import Cache, Dbase, Stats
from utils import Utils


class WinSettings(QWidget):
    def __init__(self):
        super().__init__()
        
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Настройки")
        self.setFixedSize(300, 150)

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 10, 10, 10)
        v_lay.setSpacing(10)
        self.setLayout(v_lay)

        t = "Данные загруженных изображений.\nРазмер каталогов считается отдельно."
        title_label = QLabel(t)
        v_lay.addWidget(title_label)

        h_wid = QWidget()
        v_lay.addWidget(h_wid)

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        h_wid.setLayout(h_lay)

        self.current_size = QLabel("")
        h_lay.addWidget(self.current_size)

        self.clear_btn = QPushButton("Очистить данные")
        self.clear_btn.clicked.connect(self.clear_db_cmd)
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

        current = Config.json_data.get("clear_db")
        ind = self.slider_values.index(current)

        self.slider.setValue(ind)
        self.update_label(ind)
        self.slider.valueChanged.connect(self.update_label)

    def update_label(self, index):
        value = self.slider_values[index]

        if value == 100:
            t = "Максимальный размер данных: без лимита"
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

    def clear_db_cmd(self):
        try:
            sess = Dbase.get_session()
            q = sqlalchemy.delete(Cache)
            sess.execute(q)

            q = sqlalchemy.update(Stats).where(Stats.name=="main")
            q = q.values({"size": 0})
            sess.execute(q)

            sess.commit()
            sess.execute(sqlalchemy.text("VACUUM"))
            sess.close()
            self.get_current_size()

        except Exception as e:
            print("error clear db:", e)
        

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        Config.write_json_data()
    
    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.close()


class BarBottomTree(QWidget):
    def __init__(self):
        super().__init__()

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        self.setLayout(h_lay)

        self.go_btn = QPushButton("Перейти")
        h_lay.addWidget(self.go_btn)

        self.sett_btn = QPushButton("Настройки")
        self.sett_btn.clicked.connect(self.sett_cmd)
        h_lay.addWidget(self.sett_btn)

    def sett_cmd(self):
        self.win = WinSettings()
        Utils.center_win(Utils.get_main_win(), self.win)
        self.win.show()