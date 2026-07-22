from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout

from system.items import DataItem

from ._base_widgets import UMainWidget


class WinCollage(UMainWidget):
    def __init__(self, data_items: list[DataItem]):
        super().__init__()
        self.set_always_on_top()
        self.set_close_only()

        self.central_layout = QVBoxLayout(self)
        self.central_layout.setContentsMargins(0, 0, 0, 0)

        self.resize(500, 500)
        self.img_widget = QLabel()
        self.img_widget.setStyleSheet("background: black")
        # Выравниваем по центру, чтобы при сильном растяжении окон коллаж был посередине
        self.img_widget.setAlignment(Qt.AlignmentFlag.AlignCenter) 
        self.central_layout.addWidget(self.img_widget)

        self.pixmaps: list[QPixmap] = [
            QPixmap.fromImage(i.qimages["src"])
            for i in data_items
            if i.qimages
        ]
        
        # Настройки сетки (можно вынести в параметры)
        self.spacing = 10  # Пропуск между картинками в пикселях
        self.columns = 3   # Количество колонок в сетке коллажа

    def resizeEvent(self, event):
        """Переопределяем событие изменения размера окна для авто-масштабирования."""
        super().resizeEvent(event)
        self.create_collage()

    def create_collage(self):
        if not self.pixmaps:
            return

        # 1. Считаем доступную ширину и высоту внутри QLabel
        # Вычитаем отступы, чтобы картинка не прижималась вплотную к краям окна
        margin = 20
        available_width = max(50, self.img_widget.width() - margin)
        available_height = max(50, self.img_widget.height() - margin)

        # 2. Считаем количество строк
        num_images = len(self.pixmaps)
        rows = (num_images + self.columns - 1) // self.columns

        # 3. Рассчитываем размер одной ячейки (картинки) с учетом пропусков (spacing)
        cell_width = (available_width - (self.columns - 1) * self.spacing) // self.columns
        cell_height = (available_height - (rows - 1) * self.spacing) // rows

        # Чтобы картинки не искажались, сделаем ячейки квадратными по минимальной стороне
        cell_size = min(cell_width, cell_height)
        if cell_size <= 0:
            return

        # 4. Считаем итоговые размеры самого холста коллажа
        collage_width = self.columns * cell_size + (self.columns - 1) * self.spacing
        collage_height = rows * cell_size + (rows - 1) * self.spacing

        # 5. Создаем пустой прозрачный (или черный) холст для коллажа
        collage_pixmap = QPixmap(collage_width, collage_height)
        collage_pixmap.fill(QColor(0, 0, 0, 0)) # Прозрачный фон (подложка QLabel черная)

        # 6. Рисуем сетку картинок
        painter = QPainter(collage_pixmap)
        # Включаем сглаживание, чтобы уменьшенные картинки выглядели красиво
        # painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        for index, pixmap in enumerate(self.pixmaps):
            # Координаты текущей ячейки в сетке
            col = index % self.columns
            row = index // self.columns

            x = col * (cell_size + self.spacing)
            y = row * (cell_size + self.spacing)

            # Пропорционально масштабируем исходную картинку под размер ячейки
            scaled_pix = pixmap.scaled(
                cell_size, cell_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            # Центрируем картинку внутри выделенной ей квадратной ячейки
            x_offset = (cell_size - scaled_pix.width()) // 2
            y_offset = (cell_size - scaled_pix.height()) // 2

            painter.drawPixmap(QPoint(x + x_offset, y + y_offset), scaled_pix)

        painter.end()

        # 7. Отображаем готовый коллаж в QLabel
        self.img_widget.setPixmap(collage_pixmap)

    def keyPressEvent(self, a0):
        if a0.key() == Qt.Key.Key_Escape:
            self.deleteLater()
        return super().keyPressEvent(a0)