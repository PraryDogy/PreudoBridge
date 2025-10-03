import subprocess
from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QCheckBox, QFrame, QGridLayout, QGroupBox,
                             QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                             QVBoxLayout, QWidget)

from cfg import JsonData, Static
from system.shared_utils import SharedUtils
from system.tasks import DataSizeCounter, UThreadPool

from ._base_widgets import MinMaxDisabledWin, USlider, USvgSqareWidget


class DataLimitWid(QGroupBox):
    clear_data_clicked = pyqtSignal()
    slider_w = 200
    limit_text = "Максимальный размер кэша"

    def __init__(self):
        super().__init__()

        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(5, 5, 5, 15)
        v_lay.setSpacing(10)
        self.setLayout(v_lay)

        self.total_wid = QLabel(f"{self.limit_text}")
        v_lay.addWidget(self.total_wid)

        hor_wid = QWidget()
        v_lay.addWidget(hor_wid)
        hor_lay = QHBoxLayout()
        hor_lay.setContentsMargins(0, 0, 0, 0)
        hor_wid.setLayout(hor_lay)

        slider_w = 0
        lbl_w = 65
        for k, v in Static.DATA_LIMITS.items():
            lbl = QLabel(v["text"])
            lbl.setFixedWidth(lbl_w)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            slider_w += lbl_w
            hor_lay.addWidget(lbl)

        minimum, maximum = 0, len(Static.DATA_LIMITS) - 1
        self.slider = USlider(Qt.Orientation.Horizontal, minimum, maximum)
        self.slider.valueChanged.connect(self.snap_to_step)
        self.slider.setFixedWidth(slider_w - 10)
        self.slider.setValue(JsonData.data_limit)
        v_lay.addWidget(self.slider, alignment=Qt.AlignmentFlag.AlignCenter)
        
    def snap_to_step(self, value):
        JsonData.data_limit = value


class DataSizeWid(QGroupBox):
    data_size_text = "Размер кэша:"
    files_text = "Кол-во файлов:"
    calculating = "вычисляю..."

    def __init__(self):
        super().__init__()
        
        layout = QGridLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(layout)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Создаем QLabel и сохраняем в переменные
        self.lbl_top_left = QLabel(self.data_size_text)
        self.lbl_top_right = QLabel(self.calculating)
        self.lbl_bottom_left = QLabel(self.files_text)
        self.lbl_bottom_right = QLabel(self.calculating)

        # Добавляем в сетку
        layout.addWidget(self.lbl_top_left, 0, 0)
        layout.addWidget(self.lbl_top_right, 0, 1)
        layout.addWidget(self.lbl_bottom_left, 1, 0)
        layout.addWidget(self.lbl_bottom_right, 1, 1)

        self.start_task()

    def start_task(self):

        def fin(data):
            self.lbl_top_right.setText(SharedUtils.get_f_size(data["total"]))
            self.lbl_bottom_right.setText(str(data["count"]))

        self.task_ = DataSizeCounter()
        self.task_.sigs.finished_.connect(fin)
        UThreadPool.start(self.task_)


class JsonFile(QGroupBox):
    json_text = "Показать"
    json_descr_text = "Системные файлы приложения."
    btn_w = 110

    def __init__(self):
        super().__init__()

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        self.setLayout(h_lay)

        btn_ = QPushButton(JsonFile.json_text)
        btn_.setFixedWidth(self.btn_w)
        btn_.clicked.connect(
            lambda: subprocess.call(["open", Static.APP_SUPPORT])
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

        svg_ = USvgSqareWidget(Static.INTERNAL_ICONS.get("icon.svg"), About.svg_size)
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


class SvgFrame(QWidget):
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

        self.system_theme = SvgFrame(Static.INTERNAL_ICONS.get("theme_sys.svg"), self.system_text)
        self.dark_theme = SvgFrame(Static.INTERNAL_ICONS.get("theme_dark.svg"), self.dark_text)
        self.light_theme = SvgFrame(Static.INTERNAL_ICONS.get("theme_light.svg"), self.light_text)

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
    show_texts_sig = pyqtSignal()

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

        checkbox_group = CheckboxGroup()
        checkbox_group.load_st_grid.connect(self.load_st_grid.emit)
        checkbox_group.show_texts_sig.connect(self.show_texts_sig.emit)
        main_lay.addWidget(checkbox_group)

        themes_wid = Themes()
        themes_wid.theme_changed.connect(self.theme_changed_cmd)
        main_lay.addWidget(themes_wid)

        data_limit_wid = DataLimitWid()
        data_limit_wid.clear_data_clicked.connect(self.remove_db.emit)
        main_lay.addWidget(data_limit_wid)

        data_size_wid = DataSizeWid()
        main_lay.addWidget(data_size_wid)

        json_wid = JsonFile()
        main_lay.addWidget(json_wid)

        about_wid = About()
        main_lay.addWidget(about_wid)

        self.adjustSize()

    def theme_changed_cmd(self):
        self.theme_changed.emit()
        self.adjustSize()
    
    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()

    def deleteLater(self):
        JsonData.write_config()
        super().deleteLater()