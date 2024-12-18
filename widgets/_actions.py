import os
import subprocess

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QAction, QLabel, QLineEdit, QMenu, QWidget

from cfg import Dynamic, JsonData, Static
from database import ORDER
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

REVEAL_T = "Показать в Finder"
INFO_T = "Свойства"
COPY_PATH_T = "Скопировать путь"
VIEW_T = "Просмотр"
OPEN_IN_APP_T = "Открыть в приложении"
COLORS_T = "Цвета"
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
FIND_HERE_T = "Найти здесь"
CREATE_FOLDER_T = "Создать папку"
NEW_FOLDER_T = "Новая папка"
NEW_FOLDER_WARN = "Папка с таким именем уже существует"


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
    def __init__(self, parent: QMenu, src: str, text: str):

        super().__init__(
            parent=parent,
            text=text
        )

        self.triggered.connect(self.cmd_)
        self.src = src

    def cmd_(self):
        # этот метод обязательно нужно переназначать в дочерних виджетах
        raise Exception("_actions > Переназначь cmd_")


class RevealInFinder(UAction):
    def __init__(self, parent: QMenu, src: str):

        super().__init__(
            parent=parent,
            src=src,
            text=REVEAL_T
        )

    # показывает в Finder фоном
    def cmd_(self):

        self.task_ = Task_(
            cmd_=lambda: subprocess.call(["open", "-R", self.src])
        )

        UThreadPool.start(
            runnable=self.task_
        )


class Info(UAction):
    def __init__(self, parent: QMenu, src: str):

        super().__init__(
            parent=parent,
            src=src,
            text=INFO_T
        )

    def cmd_(self):
        # импорт должен быть здесь для предотвращения circular import
        from ._base import OpenWin

        OpenWin.info(
            parent=Utils.get_main_win(),
            src=self.src
        )


# из родительского виджета копирует путь к файлу / папке
class CopyPath(UAction):
    def __init__(self, parent: QMenu, src: str):

        super().__init__(
            parent=parent,
            src=src,
            text=COPY_PATH_T
        )

    def cmd_(self):
        Utils.write_to_clipboard(
            text=self.src
        )

# просмотреть - открывает просмотрщик изображений
# или папку - тогда создается новая сетка Grid в gui.py
# посколько действие будет разным для файла / папки, здесь
# используется только сигнал для обозначения, что QAction был нажат
class View(UAction):
    _clicked = pyqtSignal()

    def __init__(self, parent: QMenu, src: str):

        super().__init__(
            parent=parent,
            src=src,
            text=VIEW_T
        )

    def cmd_(self):
        self._clicked.emit()


# это действите для GridSearch + Grid > ThumbSearch
# показать найденный ThumbSearch из GridSearch в родительской GridStandart
class ShowInFolder(UAction):
    _clicked = pyqtSignal()

    def __init__(self, parent: QMenu, src: str):

        super().__init__(
            parent=parent,
            src=src,
            text=SHOW_IN_FOLDER_T
        )

    def cmd_(self):
        self._clicked.emit()


# удалить из избранного
# за избранное отвечает меню слева - tree_favorites > TreeFavorites
class FavRemove(UAction):
    _clicked = pyqtSignal()

    def __init__(self, parent: QMenu, src: str):
        
        super().__init__(
            parent=parent,
            src=src,
            text=FAV_REMOVE_T
        )

    def cmd_(self):
        self._clicked.emit()


# Задать имя элемента в избранном - tree_favorites > TreeFavorites
class Rename(UAction):
    _clicked = pyqtSignal()

    def __init__(self, parent: QMenu, src: str):

        super().__init__(
            parent=parent,
            src=src,
            text=RENAME_T
        )

    def cmd_(self):
        self._clicked.emit()


# тоже самое что FavRemove
class FavAdd(UAction):
    _clicked = pyqtSignal()

    def __init__(self, parent: QMenu, src: str):
        super().__init__(
            parent=parent,
            src=src,
            text=FAV_ADD_T
        )

    def cmd_(self):
        self._clicked.emit()


# удаляет текущую сетку - GridStandart / GridSearch
# создает новую сетку GridStandart
# это действие нужно если мы знаем, что в папке, которую представляет сетка
# произошли какие-то изменение вне приложения
# удаление / добавление / переименование файла и т.п.
class UpdateGrid(UAction):
    def __init__(self, parent: QMenu, src: str):

        super().__init__(
            parent=parent,
            src=src,
            text=UPDATE_GRID_T
        )

    def cmd_(self):
        # удалить сетку и создать новую GridStandart
        # сигнал принимает str, где мы указываем, на основе
        # какой директории будет создана сетка GridStandart
        SignalsApp.all_.load_standart_grid.emit(JsonData.root)


# Меню со списком приложений, при помощи которых можно открыть изображение
# Например Photoshop, стандартный просмотрщик Mac Os, Capture One
# список приложений формируется при инициации приложения
# смотри cfg.py
class OpenInApp(QMenu):
    def __init__(self, parent: QMenu, src: str):

        super().__init__(
            parent=parent,
            title=OPEN_IN_APP_T
        )

        self.src = src

        # список приложений, сформированный в cfg.py при инициации приложения
        for name, app_path in Static.IMAGE_APPS.items():

            wid = QAction(
                parent=self,
                text=name
            )

            wid.triggered.connect(
                lambda e, a=app_path: self.cmd_(app_path=a, e=e)
            )

            self.addAction(wid)

    def cmd_(self, app_path: str, e):

        # открыть в приложении, путь к которому указан в app_path
        self.task_ = Task_(
            cmd_=lambda: subprocess.call(["open", "-a", app_path, self.src])
        )

        UThreadPool.start(
            runnable=self.task_
        )


# меню с цветовыми метками для _grid.py > Thumb, ThumbSearch
class ColorMenu(QMenu):
    _clicked = pyqtSignal(str)

    def __init__(self, parent: QMenu, src: str, colors: str):

        super().__init__(
            parent=parent,
            title=COLORS_T
        )

        self.src = src

        # свойство Thumb, ThumbSearch
        # цветовые метки для каждого виджета хранятся в базе данных
        # и подгружаются при создании сетки
        self.colors = colors

        # cfg.py > Static.COLORS заранее предопределенный список
        # допустимых цветовых меток
        # в цикле происходит проверка, есть ли цветовая метка
        # в self.colors (свойство Thumb, ThumbSearch)
        # если есть, то отмечается setChecked
        for color, text in Static.COLORS.items():

            wid = QAction(
                parent=self,
                text=f"{color} {text}"
            )

            wid.setCheckable(True)

            if color in self.colors:
                wid.setChecked(True)

            # клик возвращает через сигнал цветовую метку
            # виджет Thumb / ThumbSearch сверит эту метку
            # со своим списком цветовых меток (self.colors)
            # и запишет метки в базу данных
            # у виджета может быть несколько цветовых меток
            wid.triggered.connect(
                lambda e, c=color: self._clicked.emit(c)
            )

            self.addAction(wid)


# меню с рейтингом для _grid.py > Thumb, ThumbSearch
class RatingMenu(QMenu):
    _clicked = pyqtSignal(int)

    def __init__(self, parent: QMenu, src: str, rating: int):

        super().__init__(
            parent=parent,
            title=RATING_T
        )

        self.src = src

        # свойство Thumb, ThumbSearch
        # рейтинг для каждого виджета хранится в базе данных
        # и подгружается при создании сетки
        self.rating = rating

        # рейтинг от 1 до 5 звезд
        # в цикле происходит проверка, есть ли рейтинг > 0
        # в self.rating (свойство Thumb, ThumbSearch)
        # если есть, то отмечается setChecked
        # 0 возвращает False
        for rating in range(1, 6):

            wid = QAction(
                parent=self,
                text=Static.STAR_SYM * rating
            )

            wid.setCheckable(True)

            if self.rating == rating:
                wid.setChecked(True)

            # клик возвращает через сигнал целое число
            # соответствующее количеству звезд
            # например: int(5) это 5 звезд = rating в данном цикле
            # виджет Thumb / ThumbSearch установит новый рейтинг и 
            # запишет его в базу данных
            wid.triggered.connect(
                lambda e, r=rating: self._clicked.emit(r)
            )

            self.addAction(wid)


# удалить текст из виджета и скопировать в буфер обмена удаленную часть текста
# только для QLineEdit / QTextEdit
class TextCut(QAction):
    def __init__(self, parent: QMenu, widget: QLineEdit):

        super().__init__(
            parent=parent,
            text=CUT_T
        )

        self.wid = widget
        self.triggered.connect(self.cmd_)

    def cmd_(self):
        selection = self.wid.selectedText()

        # удаляем выделенный текст из виджета
        text = self.wid.text().replace(selection, "")
        self.wid.setText(text)

        Utils.write_to_clipboard(
            text=selection
        )


# Копировать выделенный текст в буфер обмена
# Допускается QLabel с возможностью выделения текста
class CopyText(QAction):
    def __init__(self, parent: QMenu, widget: QLineEdit | QLabel):

        super().__init__(
            parent=parent,
            text=COPY_T
        )

        self.wid = widget
        self.triggered.connect(self.cmd_)

    def cmd_(self):
        selection = self.wid.selectedText()

        # это два символа, которые в PyQt5 почему то обозначаются
        # символами параграфа и новой строки
        # при копировании мы удаляем их, делая копируемый текст
        # однострочным
        selection = selection.replace(Static.PARAGRAPH_SEP, "")
        selection = selection.replace(Static.LINE_FEED, "")

        Utils.write_to_clipboard(
            text=selection
        )


# Вставить текст, допускается только QLineEdit и QTextEdit
class TextPaste(QAction):
    def __init__(self, parent: QMenu, widget: QLineEdit):

        super().__init__(
            parent=parent,
            text=PASTE_T
        )

        self.wid = widget
        self.triggered.connect(self.cmd_)

    def cmd_(self):
        text = Utils.read_from_clipboard()

        # добавляем текст к существующему в виджете тексту
        new_text = self.wid.text() + text

        self.wid.setText(new_text)


# Выделить весь текст, допускается только QLineEdit и QTextEdit
class TextSelectAll(QAction):
    def __init__(self, parent: QMenu, widget: QLineEdit):

        super().__init__(
            parent=parent,
            text=SELECT_ALL_T
        )

        self.wid = widget
        self.triggered.connect(self.cmd_)

    def cmd_(self):
        self.wid.selectAll()


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

class SortMenu(QMenu):
    def __init__(self, parent: QMenu):

        super().__init__(
            parent=parent,
            title=SORT_T
        )

        ascen = QAction(
            parent=self,
            text=ASCENDING_T
        )

        # добавляем свойство прямой / обратной сортировки
        # прямая сортировка А > Я
        ascen.rev = False

        ascen.triggered.connect(
            lambda: self.cmd_revers(reversed=ascen.rev)
        )


        descen = QAction(parent=self, text=DISCENDING_T)

        # добавляем свойство прямой / обратной сортировки
        # обратная сортировка Я > А
        descen.rev = True

        descen.triggered.connect(
            lambda: self.cmd_revers(reversed=descen.rev)
        )

        for i in (ascen, descen):

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

            action_ = QAction(
                parent=self,
                text=text_name
            )

            action_.setCheckable(True)

            # передаем true_name, чтобы осуществить сортировку сетки
            # и записать true_name в пользовательские .json настройки
            action_.triggered.connect(
                lambda e, s=true_name: self.cmd_sort(true_name=s)
            )

            if Dynamic.sort == true_name:
                action_.setChecked(True)

            self.addAction(action_)

    def cmd_sort(self, true_name: str):
        # записываем true_name (тип сортировки) в пользовательский .json
        Dynamic.sort = true_name

        # переформируем текущую сетку GridStandart / SearchGrid
        # с учетом нового типа сортировки
        SignalsApp.all_.sort_grid.emit()

        # передаем сигнал в нижний бар
        # где отображается QLabel с типом сортировки
        # чтобы он обновил данные
        # пустой словарь обозначает, что нижний бар обновит данные о сортировке
        SignalsApp.all_.bar_bottom_cmd.emit({})

    def cmd_revers(self, reversed: bool):
        Dynamic.rev = reversed

        # переформируем текущую сетку GridStandart / SearchGrid
        # с учетом нового типа сортировки
        SignalsApp.all_.sort_grid.emit()

        # передаем сигнал в нижний бар
        # где отображается QLabel с типом сортировки
        # чтобы он обновил данные
        # пустой словарь обозначает, что нижний бар обновит данные о сортировке
        SignalsApp.all_.bar_bottom_cmd.emit({})


# показать сетку / список - GridStandart / GridSearch / ListFileSystem
# list_file_system.py > ListFileSystem
class ChangeView(QMenu):
    def __init__(self, parent: QMenu, src: str):

        super().__init__(
            parent=parent,
            title=CHANGE_VIEW_T
        )

        self.src = src

        # отобразить сеткой
        grid_ = QAction(
            parent=self,
            text=CHANGE_VIEW_GRID_T
        )

        grid_.triggered.connect(self.set_grid)
        grid_.setCheckable(True)
        self.addAction(grid_)

        # отобразить списком
        list_ = QAction(
            parent=self,
            text=CHANGE_VIEW_LIST_T
        )

        list_.triggered.connect(self.set_list)
        list_.setCheckable(True)
        self.addAction(list_)

        # grid_view_type отвечает за тип отображения
        # 0 отображать сеткой, 1 отображать списком

        if Dynamic.grid_view_type == 0:
            grid_.setChecked(True)

        elif Dynamic.grid_view_type == 1:
            list_.setChecked(True)

    def set_grid(self):
        Dynamic.grid_view_type = 0
        SignalsApp.all_.load_standart_grid.emit(JsonData.root)

    def set_list(self):
        Dynamic.grid_view_type = 1
        SignalsApp.all_.load_standart_grid.emit(JsonData.root)


# Найти виджет в текущей сетке виджетов по пути к файлу / папке
class FindHere(QAction):
    clicked_ = pyqtSignal()

    def __init__(self, parent: QMenu):

        super().__init__(
            parent=parent,
            text=FIND_HERE_T
        )

        self.triggered.connect(self.clicked_.emit)


class CreateFolder(QAction):
    
    def __init__(self, menu: QMenu, window: QWidget):
        super().__init__(
            parent=menu,
            text=CREATE_FOLDER_T
        )

        self.window = window
        self.triggered.connect(self.cmd_)

    def cmd_(self, *args):

        from .win_rename import WinRename

        self.win_ = WinRename(text=NEW_FOLDER_T)
        self.win_.finished_.connect(self.rename_finished)

        Utils.center_win(
            parent=self.window,
            child=self.win_
        )

        self.win_.show()

    def rename_finished(self, text: str):
        new_path = os.path.join(JsonData.root, text)

        if not os.path.exists(new_path):
            os.makedirs(new_path)
            SignalsApp.all_.load_standart_grid.emit(JsonData.root)
            SignalsApp.all_.move_to_wid_delayed.emit(new_path)

        else:

            from .win_warn import WinWarn
            self.win_warn = WinWarn(text=NEW_FOLDER_WARN)

            Utils.center_win(
                parent=self.window,
                child=self.win_warn
            )

            self.win_warn.show()