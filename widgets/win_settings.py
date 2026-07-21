import os
import subprocess
from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QPixmap
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import (QCheckBox, QGroupBox, QHBoxLayout, QLabel,
                             QSpacerItem, QVBoxLayout, QWidget)
from typing_extensions import Literal

from cfg import JsonData, Static, Themes
from system.shared_utils import SharedUtils
from system.tasks import CacheCleaner, DataSizeCounter, UThreadPool
from system.utils import Utils

from ._base_widgets import HSep, UMainWindow
# возможно в main win
from .win_warn import ConfirmWindow, WinWarn


class GroupWid(QGroupBox):
    def __init__(self):
        """
        QGroupBox + self.layout_ (vertical layout)
        """
        super().__init__()
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(6, 2, 6, 2)
        self.layout_.setSpacing(2)


class GroupChild(QWidget):
    hh = 30
    def __init__(self):
        """
        QWidget fixed height + horizontal layout
        """
        super().__init__()
        self.setFixedHeight(self.hh)
        self.layout_ = QHBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.layout_.setSpacing(0)


class SvgArrow(QSvgWidget):
    img = os.path.join(Static.internal_images_dir, "next.svg")
    size_ = 16
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.load(self.img)
        self.setFixedSize(self.size_, self.size_)

    def mouseReleaseEvent(self, a0):
        return super().mouseReleaseEvent(a0)
    

class DataSizeWidget(GroupWid):
    data_size_text = "Данные приложения:"
    files_text = "Кол-во файлов:"
    calculating = "вычисляю..."

    def __init__(self):
        super().__init__()
        self.hor_wid = GroupChild()
        self.layout_.addWidget(self.hor_wid)
        self.hor_wid.layout_.setSpacing(5)
    
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
        self.system_files_wid.mouseReleaseEvent = self.open_system_files
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

    def open_system_files(self, *args):
        subprocess.Popen(["open", Static.app_dir])

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
    icon_size = 70
    icon_path = os.path.join(Static.internal_images_dir, "icon.png")
    text_ = (
            f"{Static.app_name} {Static.app_ver}\n"
            f"{datetime.now().year} Evgeny Loshakev"
    )
    def __init__(self):
        super().__init__()

        h_lay = QHBoxLayout(self)
        h_lay.setContentsMargins(0, 0, 0, 0)

        icon = QLabel()
        pixmap = QPixmap(self.icon_path)
        pixmap = Utils.qiconed_resize(pixmap, self.icon_size)
        icon.setPixmap(pixmap)
        h_lay.addWidget(icon)

        descr = QLabel(AboutWidget.text_)
        h_lay.addWidget(descr)

        h_lay.addStretch()

class UCheckBox(QCheckBox):
    hh = 35

    def __init__(self, text: str):
        super().__init__(
            text = " " + text
        )
        self.setFixedHeight(self.hh)


class CheckboxWidgets(GroupWid):
    show_texts_sig = pyqtSignal()
    go_to_text = "\n".join([
    "Включить автоматический переход при нажатии \"Перейти\",",
    " если путь скопирован в буфер обмена.",
    ])
    show_texts_text = "Показывать подписи к кнопкам"
    left_margin = 7

    def __init__(self):
        super().__init__()

        self.enable_go_to = UCheckBox(self.go_to_text)
        self.enable_go_to.setFixedHeight(
            int(self.enable_go_to.hh * 1.5)
        )
        self.layout_.addWidget(self.enable_go_to)

        if JsonData.go_to_now:
            self.enable_go_to.setChecked(True)

        self.enable_go_to.stateChanged.connect(self.on_state_changed_two)
         
    def on_state_changed_two(self, value: int):
        data = {0: False, 2: True}
        JsonData.go_to_now = data.get(value)


class ThemeBtn(QWidget):
    clicked = pyqtSignal(str)
    ww = 70

    def __init__(self, theme: Literal["macos", "light", "dark"]):
        super().__init__()
        self.theme = theme
        self.svg = f"{Static.internal_images_dir}/{theme}_theme.svg"
        self.svg_selected = f"{Static.internal_images_dir}/{theme}_theme_selected.svg"
        text_mappings = {
            Themes.macos: Themes.macos,
            Themes.dark: "Темная",
            Themes.light: "Светлая",
        }

        self.setFixedWidth(self.ww)

        layout_ = QVBoxLayout(self)
        layout_.setContentsMargins(0, 0, 0, 0)
        layout_.setSpacing(2)
        
        self.svg_widget = QSvgWidget()
        self.svg_widget.setFixedSize(50, 50)
        layout_.addWidget(self.svg_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        label = QLabel(text_mappings[theme].capitalize())
        layout_.addWidget(label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.clear_selection()

    def select(self):
        self.svg_widget.load(self.svg_selected)

    def clear_selection(self):
        self.svg_widget.load(self.svg)

    def mouseReleaseEvent(self, a0):
        if a0.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.theme)
        return super().mouseReleaseEvent(a0)


class ThemesWidget(GroupWid):
    theme_changed = pyqtSignal()

    def __init__(self):
        super().__init__()

        self.layout_.addSpacerItem(QSpacerItem(0, 5))
        title = QLabel("Тема")
        self.layout_.addWidget(title)
        self.layout_.addSpacerItem(QSpacerItem(0, 5))
        self.layout_.addWidget(HSep())

        themes_layout = QHBoxLayout()
        themes_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        themes_layout.setContentsMargins(0, 0, 0, 0)
        self.layout_.addLayout(themes_layout)
        
        for i in (Themes.macos, Themes.dark, Themes.light):
            btn = ThemeBtn(i)
            btn.clicked.connect(lambda theme, btn=btn: self.on_btn_clicked(theme, btn))
            themes_layout.addWidget(btn)
            if i == JsonData.theme:
                btn.select()

    def on_btn_clicked(self, theme: Literal["macintosh", "light", "dark"], btn: ThemeBtn):
        theme_btns = self.findChildren(ThemeBtn)
        if theme != JsonData.theme:
            for i in theme_btns:
                i.clear_selection()
            btn.select()
            JsonData.theme = theme
            self.theme_changed.emit()


class WinSettings(UMainWindow):
    title_text = "Настройки"
    theme_changed = pyqtSignal()
    show_texts_sig = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle(WinSettings.title_text)
        self.set_always_on_top()
        self.set_close_only()
        self.setFixedWidth(470)

        main_lay = QVBoxLayout(self.centralWidget())
        main_lay.setContentsMargins(10, 0, 10, 10)
        main_lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        h_wid = QWidget()
        main_lay.addWidget(h_wid)

        checkbox_group = CheckboxWidgets()
        checkbox_group.show_texts_sig.connect(self.show_texts_sig.emit)
        main_lay.addWidget(checkbox_group)

        themes_wid = ThemesWidget()
        themes_wid.theme_changed.connect(self.theme_changed_cmd)
        main_lay.addWidget(themes_wid)

        data_size_wid = DataSizeWidget()
        main_lay.addWidget(data_size_wid)

        clickable_labels = ClickableWidgets()
        main_lay.addWidget(clickable_labels)

        about_wid = AboutWidget()
        main_lay.addWidget(about_wid)

        self.adjustSize()

    def theme_changed_cmd(self):
        self.theme_changed.emit()
        self.adjustSize()
    
    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()

    def deleteLater(self):
        JsonData.write_json_data()
        super().deleteLater()