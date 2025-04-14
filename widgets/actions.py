import os
import subprocess

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QAction, QLabel, QLineEdit, QTextEdit, QWidget

from cfg import Dynamic, Static
from database import ORDER
from utils import URunnable, UThreadPool, Utils

from ._base_widgets import UMenu

REVEAL_T = "Показать в Finder"
INFO_T = "Инфо"
COPY_PATH_T = "Скопировать путь"
VIEW_T = "Просмотр"
OPEN_IN_APP_T = "Открыть в приложении"
RATING_T = "Рейтинг"
SHOW_IN_FOLDER_T = "Показать в папке"
FAV_REMOVE_T = "Удалить из избранного"
FAV_ADD_T = "Добавить в избранное"
RENAME_T = "Переименовать"
CUT_T = "Вырезать"
COPY_T = "Копировать"
PASTE_T = "Вставить"
SELECT_ALL_T = "Выделить все"
SORT_T = "Сортировать"
ASCENDING_T = "По возрастанию"
DISCENDING_T = "По убыванию"
UPDATE_GRID_T = "Обновить"
CHANGE_VIEW_T = "Вид"
CHANGE_VIEW_GRID_T = "Сетка"
CHANGE_VIEW_LIST_T = "Список"
CREATE_FOLDER_T = "Создать папку"
NEW_FOLDER_T = "Новая папка"
NEW_FOLDER_WARN = "Папка с таким именем уже существует"
TAGS_T = "Метки"
COPY_FILES_T = "Копировать"
PASTE_FILES_T = "Вставить объекты"
DELETE_FILES_T = "Удалить"
OPEN_DEFAULT_T = "По умолчанию"


# Общий класс для выполнения действий QAction в отдельном потоке
class Task_(URunnable):
    def __init__(self,  cmd_: callable):
        super().__init__()
        self.cmd_ = cmd_

    @URunnable.set_running_state
    def run(self):

        try:
            self.cmd_()

        except RuntimeError as e:
            Utils.print_error(
                parent=None,
                error=e
            )


# Базовый QAction с обязательными аргументами
class UAction(QAction):
    def __init__(self, parent: UMenu, src: str, text: str):
        super().__init__(text, parent)

        self.triggered.connect(self.cmd_)
        self.src = src

    def cmd_(self):
        # этот метод обязательно нужно переназначать в дочерних виджетах
        raise Exception("_actions > Переназначь cmd_")


class RevealInFinder(QAction):
    def __init__(self, parent: UMenu, urls: str | list[str]):
        if isinstance(urls, str):
            self.urls = [urls]
        else:
            self.urls = urls
        t = f"{REVEAL_T} ({len(self.urls)})"
        super().__init__(t, parent)

        # если в сетке выделена одна папка, то открываем ее в Finder
        # если выделено более 1 папки/файла, то делаем Reveal 
        if len(self.urls) == 1 and os.path.isdir(self.urls[0]):
                self.triggered.connect(self.dir_cmd)
        else:
            self.triggered.connect(self.files_cmd)

    def dir_cmd(self):
        subprocess.Popen(["open", self.urls[0]])

    def files_cmd(self):        
        cmd_=lambda: subprocess.run(["osascript", Static.REVEAL_SCPT] + self.urls)
        self.task_ = Task_(cmd_)
        UThreadPool.start(self.task_)


class Info(QAction):
    def __init__(self, parent: UMenu):
        super().__init__(INFO_T, parent)


# из родительского виджета копирует путь к файлу / папке
class CopyPath(QAction):
    def __init__(self, parent: UMenu, src: str | str):

        if isinstance(src, str):
            src = [src]

        t = f"{COPY_PATH_T} ({len(src)})"

        super().__init__(t, parent)
        self.src = src
        self.triggered.connect(self.cmd_)

    def cmd_(self, *args):
        data = "\n".join(self.src)
        Utils.write_to_clipboard(text=data)


class View(QAction):
    def __init__(self, parent: UMenu):
        super().__init__(VIEW_T, parent)


class FavRemove(QAction):
    def __init__(self, parent: UMenu):
        super().__init__(FAV_REMOVE_T, parent)


class FavAdd(QAction):
    def __init__(self, parent: UMenu):
        super().__init__(FAV_ADD_T, parent)


# Меню со списком приложений, при помощи которых можно открыть изображение
# Например Photoshop, стандартный просмотрщик Mac Os, Capture One
# список приложений формируется при инициации приложения
# смотри cfg.py
class OpenInApp(UMenu):
    LIMIT = 50

    def __init__(self, parent: UMenu, src: str):

        super().__init__(parent=parent, title=OPEN_IN_APP_T)
        self.src = src

        open_default = QAction(OPEN_DEFAULT_T, parent)
        open_default.triggered.connect(self.open_default_cmd)
        self.addAction(open_default)
        self.addSeparator()
        
        self.apps: dict[str, str] = {}
        self.setup_open_with_apps()
        self.apps = dict(sorted(self.apps.items()))
        self.apps = dict(list(self.apps.items())[:OpenInApp.LIMIT])

        for name, app_path in self.apps.items():
            wid = QAction(name, self)
            cmd_ = lambda e, app_path=app_path: self.open_in_app_cmd(app_path)
            wid.triggered.connect(cmd_)
            self.addAction(wid)

    def setup_open_with_apps(self):
        for entry in os.scandir(Static.USER_APPS_DIR):
            if entry.name.endswith((".APP", ".app")):
                self.apps[entry.name] = entry.path

            elif entry.is_dir():
                for sub_entry in os.scandir(entry.path):
                    if sub_entry.name.endswith((".APP", ".app")):
                        self.apps[sub_entry.name] = sub_entry.path

    def open_in_app_cmd(self, app_path: str):
        # открыть в приложении, путь к которому указан в app_path
        cmd_=lambda: subprocess.call(["open", "-a", app_path, self.src])
        self.task_ = Task_(cmd_)
        UThreadPool.start(self.task_)

    def open_default_cmd(self):
        cmd_=lambda: subprocess.call(["open",  self.src])
        self.task_ = Task_(cmd_)
        UThreadPool.start(self.task_)


# меню с рейтингом для _grid.py > Thumb, ThumbSearch
class RatingMenu(UMenu):
    new_rating = pyqtSignal(int)

    def __init__(self, parent: UMenu, urls: str | list, current_rating: int):
        if isinstance(urls, str):
            urls = [urls]
        t = f"{RATING_T} ({len(urls)})"
        super().__init__(t, parent)

        # свойство Thumb, ThumbSearch
        # рейтинг для каждого виджета хранится в базе данных
        # и подгружается при создании сетки
        current_rating = current_rating % 10
        self.rating = current_rating

        cancel_ = QAction(Static.LINE_LONG_SYM, self)
        cancel_.triggered.connect(lambda: self.new_rating.emit(0))
        self.addAction(cancel_)

        # рейтинг от 1 до 5 звезд
        # в цикле происходит проверка, есть ли рейтинг > 0
        # в self.rating (свойство Thumb, ThumbSearch)
        # если есть, то отмечается setChecked
        # 0 возвращает False
        for current_rating in range(1, 6):
            wid = QAction(Static.STAR_SYM * current_rating, self)
            wid.setCheckable(True)

            if self.rating == current_rating:
                wid.setChecked(True)

            # клик возвращает через сигнал целое число
            # соответствующее количеству звезд
            # например: int(5) это 5 звезд = rating в данном цикле
            # виджет Thumb / ThumbSearch установит новый рейтинг и 
            # запишет его в базу данных
            cmd_ = lambda e, r=current_rating: self.new_rating.emit(r)
            wid.triggered.connect(cmd_)
            self.addAction(wid)


# меню с тегами для _grid.py > Thumb, ThumbSearch
class TagMenu(UMenu):
    new_tag = pyqtSignal(int)

    def __init__(self, parent: UMenu, urls: str, rating: int):
        if isinstance(urls, str):
            urls = [urls]
        t = f"{TAGS_T} ({len(urls)})"
        super().__init__(t, parent)
        rating = rating // 10

        # копия механик из tree_tags.py > TreeTags
        NO_TAGS_T_ = Static.LINE_LONG_SYM + " " + Static.TAGS_NO_TAGS
        DEINED_T_ = Static.DEINED_SYM + " " + Static.TAGS_DEINED
        REVIEW_T_ = Static.REVIEW_SYM  + " " + Static.TAGS_REVIEW
        APPROVED_T_ = Static.APPROVED_SYM  + " " + Static.TAGS_APPROWED

        actions = {
            NO_TAGS_T_: 9,
            DEINED_T_: 6,
            REVIEW_T_: 7,
            APPROVED_T_: 8
        }
        # конец копии

        for sym, int_ in actions.items():
            wid = QAction(sym, parent)
            wid.setCheckable(True)
            if rating == int_:
                wid.setChecked(True)
            cmd_ = lambda e, r=int_: self.new_tag.emit(r)
            wid.triggered.connect(cmd_)
            self.addAction(wid)


# удалить текст из виджета и скопировать в буфер обмена удаленную часть текста
# только для QLineEdit / QTextEdit
class CutText(QAction):
    def __init__(self, parent: UMenu, widget: QLineEdit | QTextEdit):
        super().__init__(CUT_T, parent)
        self.wid = widget
        self.triggered.connect(self.cmd_)

    def cmd_(self):
        if isinstance(self.wid, QLineEdit):
            selection = self.wid.selectedText()
            text = self.wid.text().replace(selection, "")
            self.wid.setText(text)

        elif isinstance(self.wid, QTextEdit):
            selection = self.wid.textCursor().selectedText()
            self.wid.textCursor().removeSelectedText()

        Utils.write_to_clipboard(selection)


# Копировать выделенный текст в буфер обмена
# Допускается QLabel с возможностью выделения текста
class CopyText(QAction):
    def __init__(self, parent: UMenu, widget: QLineEdit | QLabel | QTextEdit):
        super().__init__(COPY_T, parent)
        self.wid = widget
        self.triggered.connect(self.cmd_)

    def cmd_(self):
        if isinstance(self.wid, QTextEdit):
            selection = self.wid.textCursor().selectedText()
        else:
            selection = self.wid.selectedText()

        # это два символа, которые в PyQt5 почему то обозначаются
        # символами параграфа и новой строки
        # при копировании мы удаляем их, делая копируемый текст
        # однострочным
        selection = selection.replace(Static.PARAGRAPH_SEP, "")
        selection = selection.replace(Static.LINE_FEED, "")
        Utils.write_to_clipboard(selection)


# Вставить текст, допускается только QLineEdit и QTextEdit
class PasteText(QAction):
    def __init__(self, parent: UMenu, widget: QLineEdit | QTextEdit):
        super().__init__(PASTE_T, parent)
        self.wid = widget
        self.triggered.connect(self.cmd_)

    def cmd_(self):
        text = Utils.read_from_clipboard()

        if isinstance(self.wid, QTextEdit):
            cursor = self.wid.textCursor()
            cursor.insertText(text)
        else:
            new_text = self.wid.text() + text
            self.wid.setText(new_text)


# Выделить весь текст, допускается только QLineEdit и QTextEdit
class TextSelectAll(QAction):
    def __init__(self, parent: UMenu, widget: QLineEdit | QTextEdit):
        super().__init__(SELECT_ALL_T, parent)
        self.wid = widget
        self.triggered.connect(lambda: self.wid.selectAll())


# Меню, при помощи которого происходит сортировка
# сетки виджетов GridStandart / GridSearch
# Тип сортировки основан на списке ORDER из database.py
# список ORDER основан на колонках таблицы CACHE
# например: размер, дата изменения, путь к файлу и т.п.
# чтобы добавить новый тип сортировки, нужно добавить в CACHE
# новую колонку, тогда список ORDER автоматически подтянет
# новый тип сортировки
# нужно учитывать, что при изменении CACHE нужно либо очищать БД
# или осуществлять миграцию существующих данных
class SortMenu(UMenu):
    bar_bottom_update = pyqtSignal(tuple)
    order_grid_sig = pyqtSignal()
    rearrange_grid_sig = pyqtSignal()

    def __init__(self, parent: UMenu):
        super().__init__(SORT_T, parent)

        ascending = QAction(ASCENDING_T, self)
        # добавляем свойство прямой / обратной сортировки
        # прямая сортировка А > Я
        ascending.rev = False
        ascending.triggered.connect(lambda: self.cmd_revers(ascending.rev))

        descending = QAction(DISCENDING_T, self)
        # добавляем свойство прямой / обратной сортировки
        # обратная сортировка Я > А
        descending.rev = True
        descending.triggered.connect(lambda: self.cmd_revers(descending.rev))

        for i in (ascending, descending):
            i.setCheckable(True)
            self.addAction(i)

            # если свойство rev совпадает с пользовательским свойством reversed
            # то отмечаем галочкой
            # JsonData - пользовательские данные из .json файла
            if i.rev == Dynamic.rev:
                i.setChecked(True)

        self.addSeparator()

        # true_name - имя колонки CACHE
        # text_name - текстовое обозначение колонки CACHE, основанное на
        # комментарии колонки (CACHE.column.comment)
        # смотри database.py > CACHE
        for true_name, text_name in ORDER.items():

            action_ = QAction(text_name, self)
            action_.setCheckable(True)

            # передаем true_name, чтобы осуществить сортировку сетки
            # и записать true_name в пользовательские .json настройки
            cmd_ = lambda e, true_name=true_name: self.cmd_sort(true_name)
            action_.triggered.connect(cmd_)

            if Dynamic.sort == true_name:
                action_.setChecked(True)

            self.addAction(action_)

    def cmd_sort(self, true_name: str):
        # записываем true_name (тип сортировки) в пользовательский .json
        Dynamic.sort = true_name
        self.order_grid_sig.emit()
        self.rearrange_grid_sig.emit()
        self.bar_bottom_update.emit((None, None))

    def cmd_revers(self, reversed: bool):
        # записываем порядок сортировки в пользовательский .json
        Dynamic.rev = reversed
        # self.load_st_grid_sig.emit((None, None))
        self.order_grid_sig.emit()
        self.rearrange_grid_sig.emit()
        self.bar_bottom_update.emit((None, None))


# показать сетку / список - GridStandart / GridSearch / ListFileSystem
# list_file_system.py > ListFileSystem
class ChangeViewMenu(UMenu):
    change_view_sig = pyqtSignal(int)

    def __init__(self, parent: UMenu, view_index: int):
        super().__init__(CHANGE_VIEW_T, parent)

        # отобразить сеткой
        grid_ = QAction(CHANGE_VIEW_GRID_T, self)
        grid_.triggered.connect(lambda: self.change_view_sig.emit(0))
        grid_.setCheckable(True)
        self.addAction(grid_)

        # отобразить списком
        list_ = QAction(CHANGE_VIEW_LIST_T, self)
        list_.triggered.connect(lambda: self.change_view_sig.emit(1))
        list_.setCheckable(True)
        self.addAction(list_)

        # grid_view_type отвечает за тип отображения
        # 0 отображать сеткой, 1 отображать списком
        if view_index == 0:
            grid_.setChecked(True)

        elif view_index == 1:
            list_.setChecked(True)


class CopyFilesAction(QAction):
    clicked_ = pyqtSignal()

    def __init__(self, parent: UMenu, urls: list[str]):

        t = f"{COPY_FILES_T} ({len(urls)})"
        super().__init__(t, parent)
        self.triggered.connect(self.cmd_)

    def cmd_(self, *args):
        self.clicked_.emit()


class PasteFilesAction(QAction):
    clicked_ = pyqtSignal()

    def __init__(self, parent: UMenu):

        t = f"{PASTE_FILES_T} ({len(Dynamic.files_to_copy)})"
        super().__init__(t, parent)
        self.triggered.connect(self.cmd_)

    def cmd_(self, *args):
        self.clicked_.emit()


class RemoveFilesAction(QAction):
    clicked_ = pyqtSignal()

    def __init__(self, parent: UMenu, urls: list[str]):

        t = f"{DELETE_FILES_T} ({len(urls)})"
        super().__init__(t, parent)
        self.triggered.connect(self.cmd_)
        self.files = urls

    def cmd_(self, *args):
        self.clicked_.emit()
