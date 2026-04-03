import os
import subprocess
from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import (QCheckBox, QFrame, QGridLayout, QGroupBox,
                             QHBoxLayout, QLabel, QVBoxLayout, QWidget)

from cfg import JsonData, Static
from system.shared_utils import SharedUtils
from system.tasks import CacheCleaner, DataSizeCounter, UThreadPool

from ._base_widgets import HSep, MinMaxDisabledWin, ULabel, USvgSqareWidget
# возможно в main win
from .warn_win import ConfirmWindow, WinWarn


class GroupWid(QGroupBox):
    def __init__(self):
        """
        QGroupBox + self.layout_ (vertical layout)
        """
        super().__init__()
        self.layout_ = QVBoxLayout()
        self.layout_.setContentsMargins(6, 2, 6, 2)
        self.layout_.setSpacing(2)
        self.setLayout(self.layout_)


class GroupChild(QWidget):
    hh = 30
    def __init__(self):
        """
        QWidget fixed height + horizontal layout
        """
        super().__init__()
        self.setFixedHeight(self.hh)
        self.layout_ = QHBoxLayout()
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.setSpacing(0)
        self.setLayout(self.layout_)


class SvgArrow(QSvgWidget):
    clicked = pyqtSignal()
    img = "./images/next.svg"
    size_ = 16
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.load(self.img)
        self.setFixedSize(self.size_, self.size_)

    def mouseReleaseEvent(self, a0):
        self.clicked.emit()
        return super().mouseReleaseEvent(a0)
    

class DataSizeWidget(GroupWid):
    data_size_text = "Размер кэша:"
    files_text = "Кол-во файлов:"
    calculating = "вычисляю..."

    def __init__(self):
        super().__init__()
        self.hor_wid = GroupChild()
        self.layout_.addWidget(self.hor_wid)
        self.hor_wid.layout_.setSpacing(10)
    
        self.description_label = QLabel(self.data_size_text)
        self.hor_wid.layout_.addWidget(self.description_label)

        self.size_label = QLabel(self.calculating)
        self.hor_wid.layout_.addWidget(self.size_label)

        self.hor_wid.layout_.addStretch()

        self.start_task()

    def start_task(self):

        def fin(data):
            self.size_label.setText(
                SharedUtils.get_f_size(data["total"])
            )

        self.task_ = DataSizeCounter()
        self.task_.sigs.finished_.connect(fin)
        UThreadPool.start(self.task_)


class ClickableWidgets(GroupWid):
    json_descr_text = "Системные файлы приложения."
    show_descr = "Очистка данных."
    btn_w = 110

    def __init__(self):
        super().__init__()

        self.system_files_wid = GroupChild()
        self.system_files_wid.mouseReleaseEvent = (
            lambda e: subprocess.call(["open", Static.app_dir])
        )
        self.layout_.addWidget(self.system_files_wid)
        system_files_descr = QLabel(self.json_descr_text)
        self.system_files_wid.layout_.addWidget(system_files_descr)
        self.system_files_wid.layout_.addStretch()
        system_files_arrow = SvgArrow()
        self.system_files_wid.layout_.addWidget(system_files_arrow)

        self.layout_.addWidget(HSep())

        self.clear_widget = GroupChild()
        self.clear_widget.mouseReleaseEvent = (
            lambda e: self.open_clear_win()
        )
        self.layout_.addWidget(self.clear_widget)
        clear_descr = QLabel(self.show_descr)
        self.clear_widget.layout_.addWidget(clear_descr)
        self.clear_widget.layout_.addStretch()
        clear_arrow = SvgArrow()
        self.clear_widget.layout_.addWidget(clear_arrow)

    def open_clear_win(self):
        self.clear_win = ConfirmWindow(
            text=(
                "Все кэшированные изображения будут удалены. "
                "Настройки останутся без изменений."
            )
        )
        self.clear_win.center(self.window())
        self.clear_win.ok_clicked.connect(self.clear_cmd)
        self.clear_win.show()

    def open_clear_fin(self):
        self.clear_win.deleteLater()
        self.clear_fin_win = WinWarn("Очистка завершена.")
        self.clear_fin_win.setFixedSize(250, 100)
        self.clear_fin_win.center(self.window())
        self.clear_fin_win.show()

    def clear_cmd(self):
        self.clear_task = CacheCleaner()
        self.clear_task.sigs.finished_.connect(self.open_clear_fin)
        UThreadPool.start(self.clear_task)


class AboutWidget(QGroupBox):
    svg_size = 70
    text_ = (
            f"{Static.app_name} {Static.app_ver}\n"
            f"{datetime.now().year} Evgeny Loshakev"
    )
    def __init__(self):
        super().__init__()

        h_lay = QHBoxLayout()
        h_lay.setContentsMargins(0, 0, 0, 0)
        self.setLayout(h_lay)

        images = Static.internal_images_dir
        svg_ = USvgSqareWidget(
            os.path.join(images, "icon.svg"), AboutWidget.svg_size
        )
        h_lay.addWidget(svg_)

        descr = QLabel(AboutWidget.text_)
        h_lay.addWidget(descr)


class CheckboxWidgets(QGroupBox):
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


class ThemeBtn(QWidget):
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
            self.svg_container.setStyleSheet(self.border_style())
        else:
            self.svg_container.setStyleSheet(self.regular_style())

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

        images = Static.internal_images_dir
        self.system_theme = ThemeBtn(
            os.path.join(images, "theme_sys.svg"), self.system_text
        )
        self.dark_theme = ThemeBtn(
            os.path.join(images, "theme_dark.svg"), self.dark_text
        )
        self.light_theme = ThemeBtn(
            os.path.join(images, "theme_light.svg"), self.light_text
        )

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
        sender: ThemeBtn = self.sender()
        self.set_selected(sender)

        if sender == self.system_theme:
            JsonData.dark_mode = None
        elif sender == self.dark_theme:
            JsonData.dark_mode = True
        elif sender == self.light_theme:
            JsonData.dark_mode = False

        self.theme_changed.emit()

    def set_selected(self, selected_frame: ThemeBtn):
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
        self.setFixedSize(450, 480)

        main_lay = QVBoxLayout()
        main_lay.setContentsMargins(10, 0, 10, 10)
        main_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.centralWidget().setLayout(main_lay)

        h_wid = QWidget()
        main_lay.addWidget(h_wid)

        checkbox_group = CheckboxWidgets()
        checkbox_group.load_st_grid.connect(self.load_st_grid.emit)
        checkbox_group.show_texts_sig.connect(self.show_texts_sig.emit)
        main_lay.addWidget(checkbox_group)

        themes_wid = Themes()
        themes_wid.theme_changed.connect(self.theme_changed_cmd)
        main_lay.addWidget(themes_wid)

        data_size_wid = DataSizeWidget()
        main_lay.addWidget(data_size_wid)

        clickable_labels = ClickableWidgets()
        main_lay.addWidget(clickable_labels)

        about_wid = AboutWidget()
        main_lay.addWidget(about_wid)

    def theme_changed_cmd(self):
        self.theme_changed.emit()
        self.adjustSize()
    
    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()

    def deleteLater(self):
        JsonData.write_json_data()
        super().deleteLater()