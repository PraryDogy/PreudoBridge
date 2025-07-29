import os

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import (QAction, QGroupBox, QHBoxLayout, QLabel,
                             QPushButton, QVBoxLayout, QWidget, QSpacerItem)

from cfg import JsonData, Static
from system.items import MainWinItem, SearchItem

from ._base_widgets import (MinMaxDisabledWin, UFrame, ULineEdit, UMenu,
                            USvgSqareWidget, UTextEdit, WinBase)


class BarTopBtn(QWidget):
    clicked = pyqtSignal()
    width_ = 45
    big_width = 75
    height_ = 35
    svg_size = 17

    def __init__(self):
        """
        QFrame с изменением стиля при наведении курсора и svg иконкой.
        """
        super().__init__()

        self.v_lay = QVBoxLayout()
        self.v_lay.setContentsMargins(0, 0, 0, 0)
        self.v_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setLayout(self.v_lay)

        svg_frame = UFrame()
        svg_frame.setFixedSize(self.width_, self.height_)
        svg_lay = QHBoxLayout()
        svg_frame.setLayout(svg_lay)
        self.v_lay.addWidget(svg_frame, alignment=Qt.AlignmentFlag.AlignCenter)

        self.svg_btn = USvgSqareWidget(None, BarTopBtn.svg_size)
        svg_lay.addWidget(self.svg_btn)

        self.lbl = QLabel()
        self.lbl.setStyleSheet("font-size: 10px;")
        self.v_lay.addWidget(self.lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        self.lbl.hide()

    def load(self, path: str):
        self.svg_btn.load(path)

    def set_text(self, text: str):
        self.lbl.setText(text)
        self.lbl.show()

    def mouseReleaseEvent(self, a0):
        if a0.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(a0)  # Можно оставить, если родительский класс этого требует


class ListWin(MinMaxDisabledWin):
    search_place_text = "Место поиска:"
    descr_text = "Список файлов (по одному в строке):"
    ok_text = "Ок"
    cancel_text = "Отмена"
    search_place_limit = 50

    finished_ = pyqtSignal(list)

    def __init__(self, main_win_item: MainWinItem, search_item: SearchItem):
        super().__init__()
        self.set_modality()
        self.main_win_item = main_win_item
        self.search_item = search_item

        self.setLayout(self.create_main_layout())

        if isinstance(self.search_item.get_content(), list):
            self.input_.setText("\n".join(self.search_item.get_content()))

        self.adjustSize()

    def create_main_layout(self):
        v_lay = QVBoxLayout()
        v_lay.setContentsMargins(10, 5, 10, 5)
        v_lay.setSpacing(10)

        v_lay.addWidget(self.create_first_row())
        v_lay.addWidget(self.create_input_label())
        v_lay.addWidget(self.create_input_text_edit())
        v_lay.addWidget(self.create_buttons())

        return v_lay

    def create_first_row(self):
        first_row = QGroupBox()
        first_lay = QVBoxLayout()
        first_row.setLayout(first_lay)

        first_title = QLabel(ListWin.search_place_text)
        first_lay.addWidget(first_title)

        main_dir_label = QLabel(self.wrap_text(self.main_win_item.main_dir))
        first_lay.addWidget(main_dir_label)

        return first_row

    def create_input_label(self):
        return QLabel(ListWin.descr_text)

    def create_input_text_edit(self):
        self.input_ = UTextEdit()
        return self.input_

    def create_buttons(self):
        btns_wid = QWidget()
        btns_lay = QHBoxLayout()
        btns_wid.setLayout(btns_lay)

        btns_lay.addStretch()

        ok_btn = QPushButton(ListWin.ok_text)
        ok_btn.clicked.connect(self.ok_cmd)
        ok_btn.setFixedWidth(100)
        btns_lay.addWidget(ok_btn)

        can_btn = QPushButton(ListWin.cancel_text)
        can_btn.clicked.connect(self.deleteLater)
        can_btn.setFixedWidth(100)
        btns_lay.addWidget(can_btn)

        btns_lay.addStretch()

        return btns_wid

    def wrap_text(self, text: str):
        chunks = [
            text[i:i + ListWin.search_place_limit] 
            for i in range(0, len(text), ListWin.search_place_limit)
        ]
        return '\n'.join(chunks)

    def ok_cmd(self, *args):
        search_list = [i.strip() for i in self.input_.toPlainText().split("\n") if i]
        self.finished_.emit(search_list)
        self.deleteLater()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
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
        self.setPlaceholderText(SearchWidget.placeholder_text)
        self.setFixedWidth(SearchWidget.width_)
        self.textChanged.connect(self.on_text_changed)

        self.search_item = search_item
        self.main_win_item = main_win_item
        self.stop_flag: bool = False
        self.search_text: str = None
        self.search_list_local: list[str] = []

        self.input_timer = QTimer(self)
        self.input_timer.setSingleShot(True)
        self.input_timer.timeout.connect(self.prepare_text)

        self.create_menu()

    def create_menu(self):
        self.templates_menu = UMenu(parent=self)

        for text, _ in SearchItem.SEARCH_EXTENSIONS.items():
            action = QAction(text, self)
            cmd_ = lambda e, xx=text: self.setText(xx)
            action.triggered.connect(cmd_)
            self.templates_menu.addAction(action)

        search_list = QAction(SearchItem.SEARCH_LIST_TEXT, self)
        search_list.triggered.connect(self.open_search_list_win)
        self.templates_menu.addAction(search_list)

    def clear_search(self):
        """
        Очищает поиск при загрузке GridStandart:

        - Устанавливает флаг stop_flag, чтобы временно отключить реакцию на изменение текста.
        - Очищает поле ввода, SearchItem
        - Сбрасывает флаг stop_flag.

        Необходима для предотвращения повторной загрузки GridStandart,
        которая может произойти из-за сигнала textChanged при очистке поля ввода.
        """
        self.stop_flag = True
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
        if text:
            self.search_text = text
            self.input_timer.stop()
            self.input_timer.start(SearchWidget.input_timer_ms)
        else:
            self.clear_all()
            self.load_st_grid.emit()

    def clear_all(self):
        self.clear()
        self.search_item.reset()

    def prepare_text(self):
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
        self.search_text = self.search_text.strip()
        self.setText(self.search_text)
        self.search_item.reset()

        if self.search_text in SearchItem.SEARCH_EXTENSIONS:
            extensions: tuple[str] = SearchItem.SEARCH_EXTENSIONS.get(self.search_text)
            self.search_item.set_content(extensions)

        elif self.search_text == SearchItem.SEARCH_LIST_TEXT:
            self.search_item.set_content(self.search_list_local)

        else:
            self.search_item.set_content(self.search_text)

        self.load_search_grid.emit()

    def show_templates(self, a0: QMouseEvent | None) -> None:
        """
        Смотри формирование меню в инициаторе   
        Открывает меню на основе SearchItem.SEARCH_EXTENSIONS   
        При клике на пункт меню устанавливает:  
        - в окно поиска текст ключа из SearchItem.SEARCH_EXTENSIONS
        - в SearchItem.search_extensions значение соответствующего ключа    
        """
        self.templates_menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def open_search_list_win(self):
        """
        - Открывает окно для ввода списка файлов / папок для поиска   
        - Испускает сигнал finished со списком файлов из окна ввода
        """
        self.list_win = ListWin(self.main_win_item, self.search_item)
        self.list_win.finished_.connect(lambda search_list: self.list_win_finished(search_list))
        self.list_win.center(self.window())
        self.list_win.show()

    def list_win_finished(self, search_list: list[str]):
        """
        - Устанавливает значение search_list_local
        - Устанавливает текст в поле ввода
        - Срабатывает сигнал textChanged -> on_text_changed
        """
        self.search_list_local = search_list
        # чтобы перезагрузить поиск, сначала удаляем текст
        self.setText("")
        self.setText(SearchItem.SEARCH_LIST_TEXT)

    def mouseDoubleClickEvent(self, a0):
        self.show_templates(a0)
        return super().mouseDoubleClickEvent(a0)

class TopBar(QWidget):
    level_up = pyqtSignal()
    # 0 отобразить сеткой, 1 отобразить списком
    change_view = pyqtSignal(int)
    load_search_grid = pyqtSignal()
    load_st_grid = pyqtSignal()
    # при нажатии кнопкок "назад" или "вперед" загружает GridStandart
    navigate = pyqtSignal(str)
    # Кнопка "очистить данные" была нажата в окне настроек
    remove_db = pyqtSignal()
    # открывает заданный путь в новом окне
    open_in_new_win = pyqtSignal(str)
    open_settings = pyqtSignal()
    fast_sort = pyqtSignal()

    height_ = 40
    cascade_offset = 30
    history_items_limit = 100

    def __init__(self, main_win_item: MainWinItem, search_item: SearchItem):
        """
        Верхний бар в окне приложения:
        - кнопки: Назад / вперед
        - кнопка На уровень вверх
        - Открыть в новом окне
        - Показать сеткой
        - Показать списком
        - Настройки
        - Поле ввода для поиска
        """
        super().__init__()
        self.main_win_item = main_win_item
        self.search_item = search_item
        self.history_items: list[str] = []
        self.current_index = -1

        self.main_lay = QHBoxLayout()
        self.main_lay.setSpacing(0)
        self.main_lay.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_lay)

        back = BarTopBtn()
        back.load(Static.NAVIGATE_BACK_SVG)
        back.clicked.connect(lambda: self.navigate_cmd(-1))
        self.main_lay.addWidget(back)

        next = BarTopBtn()
        next.load(Static.NAVIGATE_NEXT_SVG)
        next.clicked.connect(lambda: self.navigate_cmd(1))
        self.main_lay.addWidget(next)

        level_up_btn = BarTopBtn()
        level_up_btn.clicked.connect(self.level_up.emit)
        level_up_btn.load(Static.FOLDER_UP_SVG)
        self.main_lay.addWidget(level_up_btn)

        self.main_lay.addStretch(1)
        self.main_lay.addSpacerItem(QSpacerItem(20, 0))

        self.fast_sort_btn = BarTopBtn()
        self.fast_sort_btn.load(Static.FAST_SORT_SVG)
        self.fast_sort_btn.clicked.connect(lambda: self.fast_sort.emit())
        self.main_lay.addWidget(self.fast_sort_btn)

        self.new_win_btn = BarTopBtn()
        cmd = lambda e: self.open_in_new_win.emit(self.main_win_item.main_dir)
        self.new_win_btn.mouseReleaseEvent = cmd
        self.new_win_btn.load(Static.NEW_WIN_SVG)
        self.main_lay.addWidget(self.new_win_btn)

        cascade_btn = BarTopBtn()
        cascade_btn.mouseReleaseEvent = lambda e: self.cascade_windows()
        cascade_btn.load(Static.CASCADE_SVG)
        self.main_lay.addWidget(cascade_btn)

        self.change_view_btn = BarTopBtn()
        self.change_view_btn.mouseReleaseEvent = lambda e: self.change_view_cmd()
        self.change_view_btn.mouseReleaseEvent = lambda e: self.load_st_grid.emit()
        if self.main_win_item.get_view_mode() == 0:
            self.change_view_btn.load(Static.GRID_VIEW_SVG)
        else:
            self.change_view_btn.load(Static.LIST_VIEW_SVG)
        self.main_lay.addWidget(self.change_view_btn)

        self.sett_btn = BarTopBtn()
        self.sett_btn.clicked.connect(self.open_settings.emit)
        self.sett_btn.load(Static.SETTINGS_SVG)
        self.main_lay.addWidget(self.sett_btn)

        self.main_lay.addStretch(1)
        self.main_lay.addSpacerItem(QSpacerItem(20, 0))

        self.search_wid = SearchWidget(self.search_item, self.main_win_item)
        self.search_wid.load_search_grid.connect(self.load_search_grid.emit)
        self.search_wid.load_st_grid.connect(self.load_st_grid.emit)
        self.main_lay.addWidget(self.search_wid)

        texts = [
            "Назад",
            "Вперед",
            "Наверх",
            "Сортировка",
            "Новое окно",
            "Показать все",
            "Плитка",
            "Настройки"
        ]

        if JsonData.show_text:
            self.main_lay.setSpacing(7)
            self.setFixedHeight(self.height_ + 7)
            for btn, txt in zip(self.findChildren(BarTopBtn), texts):
                btn.set_text(txt)
        else:
            self.setFixedHeight(self.height_)

        self.adjustSize()

    def change_view_cmd(self):
        if self.main_win_item.get_view_mode() == 0:
            self.change_view_btn.load(Static.LIST_VIEW_SVG)
            self.change_view_btn.set_text("Список")
            self.main_win_item.set_view_mode(1)
        else:
            self.change_view_btn.load(Static.GRID_VIEW_SVG)
            self.change_view_btn.set_text("Плитка")
            self.main_win_item.set_view_mode(0)

    def on_search_bar_clicked(self):
        if isinstance(self.search_item.get_content(), str):
            self.search_wid.selectAll()
            self.search_wid.setFocus()
        elif isinstance(self.search_item.get_content(), tuple):
            self.search_wid.selectAll()
            self.search_wid.show_templates(None)
        else:
            self.search_wid.selectAll()
            self.search_wid.open_search_list_win()

    def cascade_windows(self):
        wins = WinBase.wins
        sorted_widgets = sorted(wins, key=lambda w: w.width() * w.height(), reverse=True)

        # Начальная позиция и смещение каскада
        x, y = self.window().x(), self.window().y()
        dx, dy = TopBar.cascade_offset, TopBar.cascade_offset

        # Показываем и размещаем каскадом
        for w in sorted_widgets:
            w.move(x, y)
            x += dx
            y += dy
            w.show()
            w.raise_()

    def new_history_item(self, dir: str):
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

        if len(self.history_items) > TopBar.history_items_limit:
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
            self.main_win_item.main_dir = new_main_dir
            self.load_st_grid.emit()
