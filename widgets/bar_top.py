import os

from PyQt6.QtCore import QByteArray, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import (QGroupBox, QHBoxLayout, QLabel, QSizePolicy,
                             QSpacerItem, QVBoxLayout, QWidget)

from cfg import Dynamic, JsonData, Static
from system.items import MainWinItem, SearchItem
from system.utils import Utils

from ._base_widgets import (BaseSignals, BtnNext, BtnSmall, UFrame, ULineEdit,
                            UMainWindow, UMenu, USvgSqareWidget, UTextEdit)


class WinSearchList(UMainWindow):
    title_text = "Поиск"
    search_place_text = "Место поиска:"
    descr_text = "Вставьте текст"
    ok_text = "Ок"
    cancel_text = "Отмена"
    search_place_limit = 50
    min_w = 400
    min_h = 500
    finished_ = pyqtSignal(list)

    def __init__(self, main_win_item: MainWinItem, search_item: SearchItem):
        super().__init__()
        self.set_always_on_top()
        self.set_close_only()
        self.setMinimumSize(self.min_w, self.min_h)
        self.setWindowTitle(self.title_text)
        self.main_win_item = main_win_item
        self.search_item = search_item
        self.centralWidget().setLayout(self.create_main_layout())
        self.input_.setText(
            "\n".join(self.search_item.search_list.values())
        )
        self.adjustSize()

    def create_main_layout(self):
        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 5, 10, 5)
        v_lay.setSpacing(10)

        v_lay.addWidget(self.create_first_row())
        v_lay.addWidget(self.create_input_text_edit())
        v_lay.addWidget(self.create_convert_btn())
        v_lay.addWidget(self.create_buttons())

        return v_lay
    
    def create_first_row(self):
        first_row = QGroupBox()
        first_lay = QVBoxLayout()
        first_lay.setContentsMargins(2, 5, 2, 5)
        first_lay.setSpacing(5)
        first_row.setLayout(first_lay)

        first_title = QLabel(WinSearchList.search_place_text)
        first_lay.addWidget(first_title)

        main_dir_label = QLabel(self.wrap_text(self.main_win_item.abs_current_dir))
        first_lay.addWidget(main_dir_label)

        return first_row

    def create_input_text_edit(self):
        self.input_ = UTextEdit()
        self.input_.setPlaceholderText(
            "Введите текст (через запятую или с новой строки)"
        )
        return self.input_
    
    def create_convert_btn(self):
        btn = BtnNext("Преобразовать текст в список")
        btn.clicked.connect(self.convert_to_list)
        return btn

    def create_buttons(self):
        btns_wid = QWidget()
        btns_lay = QHBoxLayout()
        btns_lay.setContentsMargins(0, 0, 0, 0)
        btns_lay.setSpacing(10)
        btns_wid.setLayout(btns_lay)

        btns_lay.addStretch()

        ok_btn = BtnSmall(WinSearchList.ok_text)
        ok_btn.clicked.connect(self.ok_cmd)
        ok_btn.setFixedWidth(100)
        btns_lay.addWidget(ok_btn)

        can_btn = BtnSmall(WinSearchList.cancel_text)
        can_btn.clicked.connect(self.deleteLater)
        can_btn.setFixedWidth(100)
        btns_lay.addWidget(can_btn)

        btns_lay.addStretch()

        return btns_wid

    def convert_to_list(self):
        if "," in self.input_.toPlainText():
            lst = self.input_.toPlainText().split(",")
        else:
            lst = self.input_.toPlainText().split("\n")
        
        lst = [
            i.strip("\"\'\n ")
            for i in lst
            if i
        ]
        self.input_.setPlainText(
            "\n".join(lst)
        )

    def wrap_text(self, text: str):
        chunks = [
            text[i:i + WinSearchList.search_place_limit] 
            for i in range(0, len(text), WinSearchList.search_place_limit)
        ]
        return '\n'.join(chunks)

    def ok_cmd(self, *args):
        search_list = [i.strip() for i in self.input_.toPlainText().split("\n") if i]
        self.finished_.emit(search_list)
        self.deleteLater()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.deleteLater()

 
class SearchWidget(ULineEdit):
    # в MainWin посылается сигнал для загрузки GridStandart
    load_st_grid = pyqtSignal()
    # в MainWin посылается сигнал для загрузки GridSearch
    load_search_grid = pyqtSignal()
    placeholder_text = "Поиск"
    width_ = 170
    input_timer_ms = 1500

    def __init__(self, search_item: SearchItem, main_win_item: MainWinItem):
        """
        Виджет поля ввода в верхнем баре приложения.
        """
        super().__init__()
        self.setPlaceholderText(self.placeholder_text)
        self.setFixedWidth(self.width_)
        self.textChanged.connect(self.on_text_changed)
        self.clear_btn.mouseReleaseEvent = self.clear_btn_cmd

        self.search_item = search_item
        self.main_win_item = main_win_item
        self.stop_flag: bool = False
        self.search_list: list[str] = []

    def clear_btn_cmd(self, e):
        self.clear_all()
        self.load_st_grid.emit()

    def clear_search(self, *args):
        """
        Очищает поиск при загрузке GridStandart:

        - Устанавливает флаг stop_flag, чтобы временно отключить реакцию на изменение текста.
        - Очищает поле ввода, SearchItem
        - Сбрасывает флаг stop_flag.

        Необходима для предотвращения повторной загрузки GridStandart,
        которая может произойти из-за сигнала textChanged при очистке поля ввода.
        """
        self.stop_flag = True
        self.clear_btn.hide()
        self.clear_all()
        self.stop_flag = False

    def on_text_changed(self, text: str):
        """
        Обрабатывает изменения текста в поле ввода:

        - При установленном stop_flag — ничего не делает.
        - Если введён текст — запускает отложенную обработку текста через таймер.
        - Если поле пустое — очищает поиск и инициирует загрузку GridStandart.
        """
        if self.stop_flag:
            return
        self.move_clear_btn()
        self.clear_btn.show()
        self.search_list = [
            i.strip()
            for i in text.split(",")
            if i.strip()
        ]

    def clear_all(self):
        self.clear()
        self.search_item.search_list.clear()

    def start_search(self):
        """
        Готовит текст к поиску:

        - Удаляет лишние пробелы и устанавливает текст в поле ввода.
        - Сбрасывает SearchItem для нового поиска.
        - В зависимости от текста:
            - Если он соответствует ключу в SEARCH_EXTENSIONS — устанавливает расширения.
            - Если равен SEARCH_LIST_TEXT — подставляет локальный список файлов.
            - Иначе — устанавливает текст поиска.
        - Испускает сигнал начала поиска.
        """
        text = ", ".join(self.search_list)
        self.setText(text)
        self.search_item.search_list.clear()


        # самое важное тут
        # тут формируется search_list
        self.search_item.search_list.update(
            {i.lower():i for i in self.search_list}
        )
        self.load_search_grid.emit()

    def open_search_list_win(self):
        def fin(search_list: list[str]):
            self.search_list = search_list
            QTimer.singleShot(1000, self.start_search)

        self.list_win = WinSearchList(self.main_win_item, self.search_item)
        self.list_win.finished_.connect(lambda search_list: fin(search_list))
        self.list_win.center(self.window())
        self.list_win.show()
        QTimer.singleShot(0, self.deselect)

    def mouseDoubleClickEvent(self, a0):
        self.open_search_list_win()
        return super().mouseDoubleClickEvent(a0)

    def keyPressEvent(self, a0):
        if a0.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            self.start_search()
        return super().keyPressEvent(a0)
    

class BarTopBtn(QWidget):
    clicked = pyqtSignal()
    svg_size = 30

    def __init__(self, filename: str):
        super().__init__()
        self.setFixedWidth(65)
        # self.setStyleSheet("background: red")
        self.normal_svg_data = None
        self.solid_svg_data = None

        self.v_lay = QVBoxLayout(self)
        self.v_lay.setContentsMargins(0, 0, 0, 0)
        self.v_lay.setSpacing(1)
        self.v_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.svg_btn = QSvgWidget()
        self.svg_btn.setFixedSize(self.svg_size, self.svg_size)
        self.v_lay.addWidget(self.svg_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.lbl = QLabel()
        self.lbl.setStyleSheet("font-size: 10px;")
        self.v_lay.addWidget(self.lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        self.load_svg_data(filename)
        self.set_normal_style()

    def load_svg_data(self, filename: str):
        normal_path = os.path.join(
            Static.internal_images_dir,
            filename + ".svg"
        )
        solid_path = os.path.join(
            Static.internal_images_dir,
            filename + "_selected.svg"
        )
        with open(normal_path, "rb") as f:
            self.normal_svg_data = QByteArray(f.read())
        with open(solid_path, "rb") as f:
            self.solid_svg_data = QByteArray(f.read())

    def set_solid_style(self):
        self.svg_btn.load(self.solid_svg_data)

    def set_normal_style(self):
        self.svg_btn.load(self.normal_svg_data)
    
    def mouseReleaseEvent(self, a0):
        self.clicked.emit()
        return super().mouseReleaseEvent(a0)
    
    def enterEvent(self, event):
        self.set_solid_style()
        return super().enterEvent(event)
    
    def leaveEvent(self, a0):
        self.set_normal_style()
        return super().leaveEvent(a0)


class BackBtn(BarTopBtn):
    def __init__(self):
        super().__init__("back")
        self.lbl.setText("Назад")


class ForwardBtn(BarTopBtn):
    def __init__(self):
        super().__init__("forward")
        self.lbl.setText("Вперед")


class LevelUpBtn(BarTopBtn):
    def __init__(self):
        super().__init__("level_up")
        self.lbl.setText("Наверх")


class UpdateBtn(BarTopBtn):
    def __init__(self):
        super().__init__("update")
        self.lbl.setText("Обновить")


class NewFolderBtn(BarTopBtn):
    def __init__(self):
        super().__init__("new_folder")
        self.lbl.setText("Новая папка")


class ViewBtn(BarTopBtn):
    def __init__(self):
        super().__init__("list_view")
        self.lbl.setText("Список")


class SettingsBtn(BarTopBtn):
    def __init__(self):
        super().__init__("settings")
        self.lbl.setText("Настройки")



class BarTop(QWidget):
    load_search_grid = pyqtSignal()
    hh = 60
    history_items_limit = 100

    def __init__(self, main_win_item: MainWinItem, search_item: SearchItem):
        super().__init__()
        self.setFixedHeight(self.hh)

        self.base_signals = BaseSignals()
        self.main_win_item = main_win_item
        self.search_item = search_item
        self.history_items: list[str] = []
        self.current_index = -1

        self.main_lay = QHBoxLayout(self)
        self.main_lay.setContentsMargins(0, 3, 0, 3)
        self.main_lay.setSpacing(0)

        back = BackBtn()
        back.clicked.connect(lambda: self.navigate_cmd(-1))
        self.main_lay.addWidget(back)

        next = ForwardBtn()
        next.clicked.connect(lambda: self.navigate_cmd(1))
        self.main_lay.addWidget(next)

        level_up_btn = LevelUpBtn()
        level_up_btn.clicked.connect(self.base_signals.level_up.emit)
        self.main_lay.addWidget(level_up_btn)

        self.main_lay.addStretch(1)

        self.update_btn = UpdateBtn()
        self.update_btn.clicked.connect(lambda: self.base_signals.load_st_grid.emit(self.main_win_item.abs_current_dir))
        self.main_lay.addWidget(self.update_btn)

        self.new_folder_btn = NewFolderBtn()
        self.new_folder_btn.clicked.connect(lambda: self.base_signals.new_folder.emit())
        self.main_lay.addWidget(self.new_folder_btn)

        self.change_view_btn = ViewBtn()
        self.change_view_btn.clicked.connect(lambda: self.base_signals.change_view.emit())
        self.main_lay.addWidget(self.change_view_btn)

        self.sett_btn = SettingsBtn()
        self.sett_btn.clicked.connect(self.base_signals.settings.emit)
        self.main_lay.addWidget(self.sett_btn)

        self.main_lay.addStretch(1)

        self.search_wid = SearchWidget(self.search_item, self.main_win_item)
        self.search_wid.load_search_grid.connect(self.load_search_grid.emit)
        self.search_wid.load_st_grid.connect(
            lambda: self.base_signals.load_st_grid.emit(self.main_win_item.abs_current_dir)
        )
        self.main_lay.addWidget(self.search_wid)

    def history_item(self, dir: str):
        """
        Добавляет новый путь в историю навигации:

        - Если текущий индекс не на последнем элементе истории, значит пользователь
        отклонился от ветки (перешёл назад и открыл новую папку). В этом случае
        удаляются все элементы после текущего положения: текущий индекс меняется
        в функции navigate_cmd
        - Ограничиваем размер истории 100 элементами.
        - Добавляем новый путь в конец истории.
        - Устанавливаем текущий индекс на последний элемент истории, который был добавлен.

        Пример:
        1. История: ["A", "B", "C"]
        - Текущий индекс: 2 (на "C")
        2. Пользователь нажал "назад", теперь текущий индекс на "B" (индекс 1).
        3. Пользователь открыл новую папку "B2".
        - Так как текущий индекс не на конце истории, мы обрезаем "C", и новая история:
            ["A", "B"]
        4. Добавляем "B2" в конец истории.
        - Новая история: ["A", "B", "B2"]
        - Текущий индекс теперь указывает на "B2" (индекс 2).
        
        Это позволяет предотвратить сохранение старых путей, если пользователь изменил
        направление навигации (например, вернулся назад и затем открыл новую папку).
        """

        if dir == os.sep:
            return

        # Проверяем, отклонился ли пользователь от текущей ветки истории:
        # Если текущий индекс не на последнем элементе списка,
        # значит пользователь перешёл назад и открыл новую папку,
        # поэтому нужно удалить все элементы, которые шли после текущего положения.
        if self.current_index < len(self.history_items) - 1:
            # Убираем все элементы после текущего индекса, чтобы не сохранялись
            # старые пути, если пользователь изменил направление навигации.
            self.history_items = self.history_items[:self.current_index + 1]

        if len(self.history_items) > BarTop.history_items_limit:
            self.history_items.pop(0)
            self.current_index -= 1

        self.history_items.append(dir)
        self.current_index = len(self.history_items) - 1

    def navigate_cmd(self, offset: int):
        """
        Перемещается по истории директорий, изменяя текущую позицию:

        - Параметр `offset` определяет направление навигации:
            - `offset = -1` — переход на один элемент назад в истории.
            - `offset = 1` — переход на один элемент вперёд в истории.
        - Проверяет, что новый индекс находится в допустимом диапазоне истории:
            - Индекс должен быть в пределах от 0 до длины истории минус 1.
        - Если переход возможен, обновляет текущий индекс и эмиттирует сигнал с новым путём для загрузки.
        
        Пример работы:
        - Если мы находимся в директории "B" (индекс 1), и вызван `navigate_cmd(-1)`, то мы перемещаемся в "A" (индекс 0).
        - Если вызван `navigate_cmd(1)`, то мы возвращаемся в "B" (индекс 1), если было возможно двигаться вперёд.
    """

        new_index = self.current_index + offset
        if 0 <= new_index < len(self.history_items):
            self.current_index = new_index
            new_main_dir = self.history_items[self.current_index]
            self.base_signals.load_st_grid.emit(new_main_dir)
