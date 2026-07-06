import os
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QLabel, QApplication, QMessageBox

class ThemeChooserWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выбор темы оформления")
        self.resize(300, 400)
        
        # Путь к папке с темами
        self.themes_dir = "./themes"
        
        # Настройка интерфейса
        layout = QVBoxLayout(self)
        
        label = QLabel("Выберите тему из списка:")
        layout.addWidget(label)
        
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        
        # Загружаем доступные файлы тем в список
        self.load_themes()
        
        # Подключаем событие клика по элементу списка
        self.list_widget.itemClicked.connect(self.apply_selected_theme)

    def load_themes(self):
        """Сканирует папку ./themes и добавляет qss-файлы в список"""
        if not os.path.exists(self.themes_dir):
            # Если папки нет, создадим её автоматически для удобства
            os.makedirs(self.themes_dir)
            
        # Ищем все файлы с расширением .qss
        try:
            files = [f for f in os.listdir(self.themes_dir) if f.endswith('.qss')]
            if not files:
                self.list_widget.addItem("Темы не найдены (.qss)")
                self.list_widget.setEnabled(False)
            else:
                self.list_widget.addItems(files)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось прочитать папку тем:\n{str(e)}")

    def apply_selected_theme(self, item):
        """Считывает выбранный QSS-файл и применяет его глобально"""
        theme_name = item.text()
        theme_path = os.path.join(self.themes_dir, theme_name)
        
        if not os.path.exists(theme_path):
            return

        try:
            with open(theme_path, "r", encoding="utf-8") as f:
                qss_content = f.read()
                
            # Главная магия: применяем стиль ко ВСЕМУ приложению на лету
            QApplication.instance().setStyleSheet(qss_content)
            
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить тему {theme_name}:\n{str(e)}")
