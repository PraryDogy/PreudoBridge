import os
import traceback

import sqlalchemy
from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QCloseEvent, QPixmap
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import QLabel
from sqlalchemy.exc import IntegrityError, OperationalError

from cfg import JsonData, Static
from database import CACHE, Dbase, OrderItem
from signals import SignalsApp
from utils import URunnable, UThreadPool, Utils

from ._finder_items import FinderItems, LoadingWid
from ._grid import Grid, Thumb, ThumbFolder
from ._grid_tools import GridTools

WARN_TEXT = "Нет изображений или нет подключения к диску"
TASK_NAME = "LOAD_IMAGES"
SQL_ERRORS = (IntegrityError, OperationalError)


class WorkerSignals(QObject):
    new_widget = pyqtSignal(OrderItem)


class LoadImages(URunnable):
    def __init__(self, order_items: list[OrderItem]):
        super().__init__()

        self.signals_ = WorkerSignals()
        self.order_items = [
            i
            for i in order_items
            # if i.type_ != Static.FOLDER_TYPE
        ]

    @URunnable.set_running_state
    def run(self):

        # чтобы не создавать пустую ДБ в пустых или папочных директориях

        if not self.order_items:
            return

        db = os.path.join(JsonData.root, Static.DB_FILENAME)
        self.dbase = Dbase()
        engine = self.dbase.create_engine(path=db)

        if engine is None:
            return

        self.conn = engine.connect()

        try:
            self.main()
        except RuntimeError as e:
            Utils.print_error(parent=None, error=e)

        self.conn.close()

    def main(self):
        self.process_order_items()
        self.process_removed_items()

    def process_order_items(self):

        for order_item in self.order_items:
            
            try:

                new_order_item = GridTools.update_order_item(
                    conn=self.conn,
                    order_item=order_item
                )

                if new_order_item:
                    self.signals_.new_widget.emit(new_order_item)

            except Exception as e:
                Utils.print_error(parent=self, error=e)
                # print(traceback.format_exc())
                continue

    def process_removed_items(self):

        q = sqlalchemy.select(CACHE.c.id, CACHE.c.name)
        res = self.conn.execute(q).fetchall()

        order_items = [
            Utils.hash_filename(filename=i.name)
            for i in self.order_items
        ]

        del_items: list[int] = []

        for id, name in res:
            if name not in order_items:
                del_items.append(id)

        for id_ in del_items:

            q = sqlalchemy.delete(CACHE)
            q = q.where(CACHE.c.id == id_)

            try:
                self.conn.execute(q)

            except SQL_ERRORS as e:
                Utils.print_error(parent=self, error=e)
                self.conn.rollback()
                continue

        try:
            self.conn.commit()

        except SQL_ERRORS as e:
            Utils.print_error(parent=self, error=e)
            self.conn.rollback()


class GridStandart(Grid):
    def __init__(self, width: int, prev_path: str = None):

        super().__init__(
            width=width,
            prev_path=prev_path
        )

        self.order_items: list[OrderItem] = []
        self.tasks: list[LoadImages] = []

        self.offset = 0
        self.limit = 100

        self.loading_lbl = LoadingWid(parent=self)
        Utils.center_win(self, self.loading_lbl)
        self.show()

        self.finder_task = FinderItems()
        self.finder_task.signals_.finished_.connect(self.finder_task_fin)
        UThreadPool.start(self.finder_task)

        self.verticalScrollBar().valueChanged.connect(self.on_scroll)

    def on_scroll(self, value: int):

        if value == self.verticalScrollBar().maximum():

            if self.offset > self.total:
                return
            else:
                self.offset += self.limit
                self.create_sorted_grid()

    def finder_task_fin(self, order_items: list[OrderItem]):

        self.loading_lbl.hide()
        self.order_items = order_items
        self.total = len(order_items)

        SignalsApp.instance.bar_bottom_cmd.emit(
            {"src": JsonData.root, "total": self.total}
        )

        self.create_sorted_grid()

    def create_sorted_grid(self):

        sys_disk = os.path.join(os.sep, "Volumes", "Macintosh HD")
        col_count = Utils.get_clmn_count(self.ww)
        row, col = 0, 0

        Thumb.calculate_size()

        cut = self.order_items[self.offset:self.offset + self.limit]

        for order_item in cut:

            if os.path.isdir(order_item.src):

                wid = ThumbFolder(
                    src=order_item.src,
                    size=order_item.size,
                    mod=order_item.mod,
                    rating=order_item.rating,
                    )

                if os.path.ismount(order_item.src) or order_item.src == sys_disk:
                    img_wid = wid.img_frame.findChild(QSvgWidget)
                    img_wid.load(Static.HDD_SVG)


            else:
                wid = Thumb(
                    src=order_item.src,
                    size=order_item.size,
                    mod=order_item.mod,
                    rating=order_item.rating,
                    )

            wid.clicked_.connect(
                lambda w=wid: self.select_one_wid(wid=w)
            )
        
            wid.control_clicked.connect(
                lambda w=wid: self.control_clicked(wid=w)
            )

            wid.shift_clicked.connect(
                lambda w=wid: self.shift_clicked(wid=w)
            )

            wid.open_in_view.connect(
                lambda w=wid: self.open_in_view(wid=w)
            )

            wid.mouse_moved.connect(
                lambda w=wid: self.drag_thumb(wid=w)
            )

            self.add_widget_data(
                wid=wid,
                row=row,
                col=col
            )

            self.grid_layout.addWidget(wid, row, col)

            col += 1
            if col >= col_count:
                col = 0
                row += 1

        if self.cell_to_wid:
            self.start_load_images(cut)

        elif not os.path.exists(JsonData.root):
            setattr(self, "no_images", WARN_TEXT)

        elif not self.cell_to_wid:
            setattr(self, "no_images", WARN_TEXT)

        if hasattr(self, "no_images"):
            no_images = QLabel(text=getattr(self, "no_images"))
            no_images.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(no_images, 0, 0)

        self.order_()
        self.select_after_list()
        
    def start_load_images(self, cut_order_items: list[OrderItem]):
        self.load_images_task_ = LoadImages(order_items=cut_order_items)
        self.load_images_task_.set_name(text=TASK_NAME)
        cmd_ = lambda image_data: self.set_pixmap(image_data)
        self.load_images_task_.signals_.new_widget.connect(cmd_)
        UThreadPool.start(self.load_images_task_)
    
    def set_pixmap(self, order_item: OrderItem):

        widget = Thumb.path_to_wid.get(order_item.src)

        if isinstance(widget, Thumb):

            if isinstance(order_item.pixmap_, QPixmap):
                widget.set_pixmap(pixmap=order_item.pixmap_)

            if isinstance(order_item.rating, int):
                widget.set_rating(rating=order_item.rating)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        
        for task in UThreadPool.current:
            if task.get_name() == TASK_NAME:
                task.should_run = False

        return super().closeEvent(a0)

    def resizeEvent(self, a0):
        Utils.center_win(self, self.loading_lbl)
        return super().resizeEvent(a0)