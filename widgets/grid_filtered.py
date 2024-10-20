import os

import sqlalchemy
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QPixmap
from PyQt5.QtWidgets import QLabel

from cfg import Config, JsonData
from database import CACHE, Engine
from utils import Utils

from .grid_base import Grid, Thumbnail


class LoadDbItems(QThread):
    _finished = pyqtSignal(list)

    def __init__(self):
        super().__init__()

    def run(self):
        # загружаем данные соответствуя порядку в Config.ORDER за исключением
        # img, src (по ним не производится сортировка сетки)
        q = sqlalchemy.select(CACHE.c.img, CACHE.c.src, CACHE.c.size, CACHE.c.modified, CACHE.c.colors, CACHE.c.rating)
        q = q.where(CACHE.c.root == JsonData.root)
        
        if Config.color_filters:
            color_filters = list(Config.color_filters)
            queries = [
                CACHE.c.colors.like(f"%{colorr}%")
                for colorr in color_filters
                ]
            q = q.where(sqlalchemy.or_(*queries))

        if Config.rating_filter:
            q = q.where(sqlalchemy.and_(CACHE.c.rating > 0, Config.rating_filter >= CACHE.c.rating))

        with Engine.engine.connect() as conn:
            res = conn.execute(q).fetchall()

        items = []
        for img, src, size, modified, colors, rating in res:
            img = Utils.pixmap_from_bytes(img)
            filename: str = os.path.basename(src)
            type = filename.split(".")[-1]

            # кортеж соответствует порядку в Config.ORDER за исключением 
            # img, src, filename (по ним не производится сортировка сетки)
            item = (img, src, filename, size, modified, type, colors, rating)
            items.append(item)

        items = self.sort_items(items)
        self._finished.emit(items)

    def sort_items(self, db_items: list):
        # (img, src, filename, size, modified, filetype, colors, rating) - db_items
        # {'img': 0, 'src': 1, 'filename': 2, 'name': 3, 'size': 4, 'modify': 5, 'type': 6, 'colors': 7, 'rating': 8} - sort_data
        # если сортировка JsonData.sort будет "size"
        # то индекс будет 4
        # и произойдет сортировка db_items по индексу 4, он же size

        sort_data = {
            "img": 0,
            "src": 1,
            "filename": 2,
            **{
                key: x
                for x, key in enumerate(Config.ORDER, 3)
            }
            }
        
        index = sort_data.get(JsonData.sort)
        rev = JsonData.reversed

        if index != 5:
            sort_key = lambda x: x[index]
        else:
            sort_key = lambda x: len(x[index])

        return sorted(db_items, key=sort_key, reverse=rev)


class GridFiltered(Grid):
    def __init__(self, width: int):
        super().__init__(width)
        self.ww = width

        self.finder_thread = LoadDbItems()
        self.finder_thread._finished.connect(self.create_grid)
        self.finder_thread.start()

    def create_grid(self, finder_items: list):
        col_count = Utils.get_clmn_count(self.ww)
        row, col = 0, 0

        for img, src, filename, size, modified, type, colors, rating in finder_items:

            wid = Thumbnail(filename, src, self.path_to_wid)
            wid.move_to_wid.connect(lambda src: self.move_to_wid(src))
            self.set_pixmap(wid, img)
            wid.set_colors(colors)
            wid.set_rating(rating)

            self.grid_layout.addWidget(wid, row, col)
            wid.clicked.connect(lambda r=row, c=col: self.select_new_widget((r, c)))

            # добавляем местоположение виджета в сетке для навигации клавишами
            self.cell_to_wid[row, col] = wid
            self.path_to_wid[src] = wid

            col += 1
            if col >= col_count:
                col = 0
                row += 1

        self.wid_to_cell = {v: k for k, v in self.cell_to_wid.items()}

        if not self.cell_to_wid:
            t = f"{JsonData.root}\nНет изображений"
            if Config.color_filters:
                t = f"{t} с фильтрами: {''.join(Config.color_filters)}"
            if Config.rating_filter > 0:
                stars = '\U00002605' * Config.rating_filter
                t = f"{t}\nС рейтингом: {stars}"
            setattr(self, "no_images", t)

        if hasattr(self, "no_images"):
            no_images = QLabel(t)
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0)
    
    def set_pixmap(self, widget: Thumbnail, image: QPixmap):
        if isinstance(image, QPixmap):
            widget.img_label.setPixmap(image)

    # метод вызывается если была изменена сортировка или размер окна
    # тогда нет необходимости заново делать обход в Finder и грузить изображения
    # здесь только пересортируется сетка
    def resize_grid(self, width: int):

        # копируем для итерации виджетов
        # нам нужны только значения ключей, там записаны виджеты
        coords = self.cell_to_wid.copy()

        # очищаем для нового наполнения
        self.cell_to_wid.clear()
        self.wid_to_cell.clear()
        self.curr_cell = (0, 0)

        # получаем новое количество колонок на случай изменения размера окна
        col_count = Utils.get_clmn_count(width)
        row, col = 0, 0

        for (_row, _col), wid in coords.items():        
            if isinstance(wid, Thumbnail):
                wid.disconnect()
                wid.move_to_wid.connect(lambda src: self.move_to_wid(src))

            wid.clicked.connect(lambda r=row, c=col: self.select_new_widget((r, c)))
            self.grid_layout.addWidget(wid, row, col)
            self.cell_to_wid[row, col] = wid

            col += 1
            if col >= col_count:
                col = 0
                row += 1

        self.wid_to_cell = {v: k for k, v in self.cell_to_wid.items()}

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        return super().closeEvent(a0)