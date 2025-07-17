

class SortItem:
    """
    Класс, содержащий перечень доступных атрибутов для сортировки элементов.

    Правила добавления/удаления атрибута:

    - Каждый атрибут задаётся как строковая константа (например, name = "name"),
      чтобы избежать ручного ввода строк по всему коду. Вместо строки "name" 
      можно использовать Sort.name — это безопаснее и удобнее при поддержке проекта.

    - Словарь `items` содержит список доступных сортировок:
        • ключ — техническое имя поля, берётся из атрибутов класса Sort (например, Sort.name);
        • значение — человекочитаемое название, отображаемое в интерфейсе (например, "Имя").

    - При добавлении или удалении атрибута:
        • добавьте/удалите соответствующую строковую константу в классе Sort;
        • добавьте/удалите соответствующую запись в словаре `items`;
        • обязательно добавьте/удалите соответствующий атрибут в классе BaseItem.

    Пример добавления нового поля сортировки:
    - Нужно добавить сортировку по дате последнего открытия.
        • Добавьте в Sort: `last_open = "last_open"`
        • Добавьте в items: `last_open: "Дата последнего открытия"`
        • Добавьте в BaseItem: `self.last_open = None`
        • Реализуйте логику заполнения поля, например, через os.stat
    """

    name = "name"
    type_ = "type_"
    size = "size"
    mod = "mod"
    birth = "birth"
    rating = "rating"

    lang_dict: dict[str, str] = {
        name : "Имя",
        type_ : "Тип",
        size : "Размер",
        mod : "Дата изменения",
        birth: "Дата создания",
        rating : "Рейтинг",
    }

    def __init__(self):
        """
        Объект для сортировки. По умолчанию: sort "name", rev False
        """
        super().__init__()
        self.sort: str = SortItem.name
        self.rev: bool = False

    def set_rev(self, value: bool):
        if isinstance(value, bool):
            self.rev = value
        else:
            raise Exception("только bool")
        
    def get_rev(self):
        return self.rev

    def set_sort(self, value: str):
        if isinstance(value, str):
            self.sort = value
        else:
            raise Exception("только str")
        
    def get_sort(self):
        return self.sort


class BaseItem:
    def __init__(self, src: str, rating: int = 0):
        """
        Вызовите setup_attrs после инициации экземпляра класса.     

        Базовый виджет, предшественник grid.py > Thumb.
        Используется для передачи данных между потоками и функциями.

        Пример использования:
        - В дополнительном потоке создаётся экземпляр класса BaseItem
        - Экземпляру присваивается имя "TEST" через атрибут name.
        - Этот экземпляр передаётся в основной поток через сигнал.
        - В основном потоке создаётся экземпляр класса Thumb (из модуля grid.py).
        - Атрибут name у Thumb устанавливается на основе значения BaseItem.name ("TEST").

        В BaseItem обязаны присутствовать все аттрибуты, соответствующие Sort.items
        """
        super().__init__()
        self.src: str = src
        self.name: str = None
        self.type_: str = None
        self.rating: int = rating
        self.mod: int = None
        self.birth: int = None
        self.size: int = None
        self.pixmap_storage: QPixmap = None

    def set_pixmap_storage(self, pixmap: QPixmap):
        """
        Сохраняет QPixmap, переданный, например, из дополнительного потока в основной.
        """
        self.pixmap_storage = pixmap

    def get_pixmap_storage(self):
        """
        Возвращает ранее сохранённый QPixmap.
        """
        return self.pixmap_storage

    def setup_attrs(self):
        """
        Устанавливает параметры: src, name, type_, mod, birth, size, rating
        """
        self.src = Utils.normalize_slash(self.src)
        self.name = os.path.basename(self.src)

        if os.path.isdir(self.src):
            self.type_ = Static.FOLDER_TYPE
        else:
            _, self.type_ = os.path.splitext(self.src)

        stat = os.stat(self.src)
        self.mod = stat.st_mtime
        self.birth = stat.st_birthtime
        self.size = stat.st_size

        # Поправка старой системы рейтинга, когда рейтинг был двузначным
        self.rating = self.rating % 10

    @classmethod
    def check(cls):
        """
        Проверяет, содержит ли экземпляр BaseItem все атрибуты, 
        имена которых указаны в ключах словаря Sort.items.

        Это необходимо для корректной сортировки, так как она выполняется 
        по атрибутам, соответствующим ключам Sort.items.
        """
        base_item = BaseItem("/no/path/file.txt")
        for column_name, _ in SortItem.lang_dict.items():
            if not hasattr(base_item, column_name):
                raise Exception (f"\n\nbase_widgets.py > BaseItem: не хватает аттрибута из Sort.items. Аттрибут: {column_name}\n\n")

    @classmethod
    def sort_(cls, base_items: list["BaseItem"], sort_item: SortItem) -> list["BaseItem"]:
        """
        Выполняет сортировку списка объектов BaseItem по заданному атрибуту.

        Пример:
        - Пользователь выбирает тип сортировки, например "По размеру", в меню SortMenu (actions.py).
        - SortMenu формируется на основе словаря Sort.items (в этом файле, выше).
        - Выбранный пункт "По размеру" соответствует ключу "size" в Sort.items.
        - Ключ "size" — это имя атрибута в классе BaseItem.
        - Таким образом, сортировка осуществляется по значению атрибута "size" у объектов BaseItem.
        """
        
        attr = sort_item.sort
        rev = sort_item.rev

        if attr == SortItem.name:

            # Особый случай: сортировка по имени
            # Разделяем элементы на две группы:
            # - те, чьё имя начинается с цифры (nums)
            # - все остальные (abc)
            nums: list[BaseItem] = []
            abc: list[BaseItem] = []

            for i in base_items:

                if i.name[0].isdigit():
                    nums.append(i)

                else:
                    abc.append(i)

            # Сортировка числовых имён по значению начальных цифр
            key_num = lambda base_item: cls.get_nums(base_item)

            # Сортировка остальных по алфавиту (по атрибуту 'name')
            key_abc = lambda base_item: getattr(base_item, attr)

            nums.sort(key=key_num, reverse=rev)
            abc.sort(key=key_abc, reverse=rev)

            # Объединяем отсортированные списки: сначала числовые, потом буквенные
            return [*nums, *abc]

        else:
            # Обычная сортировка по значению заданного атрибута
            key = lambda base_item: getattr(base_item, attr)
            base_items.sort(key=key, reverse=rev)
            return base_items

    @classmethod
    def get_nums(cls, base_item: "BaseItem"):
        """
        Извлекает начальные числа из имени base_item для числовой сортировки.
        Например: "123 Te99st33" → 123
        """
        return int(re.match(r'^\d+', base_item.name).group())
    




class SearchItem:
    SEARCH_LIST_TEXT = "Найти по списку"
    SEARCH_EXTENSIONS = {
        "Найти jpg": Static.ext_jpeg,
        "Найти png": Static.ext_png,
        "Найти tiff": Static.ext_tiff,
        "Найти psd/psb": Static.ext_psd,
        "Найти raw": Static.ext_raw,
        "Найти видео": Static.ext_video,
        "Найти любые фото": Static.ext_all
    }

    def __init__(self):
        super().__init__()
        self._filter: int = 0
        self._content: str | list[str] = None

    def get_content(self):
        """
        none    
        str: искать текст   
        tuple[str]: искать по расширениям   
        list[str]: искать по списку 
        """
        return self._content

    def set_content(self, value: str | tuple[str] | list[str]):
        """
        none    
        str: искать текст   
        tuple: искать по расширениям    
        list[str]: искать по списку     
        """
        self._content = value
    
    def set_filter(self, value: int):
        """
        0: нет фильтра      
        1: точное соответствие  
        2: искомый текст содержится в имени и наоборот  
        """
        self._filter = value

    def get_filter(self):
        """
        0: нет фильтра  
        1: точное соответствие  
        2: искомый текст содержится в имени и наоборот  
        """
        return self._filter
    
    def reset(self):
        self.set_content(None)
        self.set_filter(0)


class MainWinItem:
    def __init__(self):
        self._urls: list[str] = []
        self._go_to: str = None
        self.main_dir: str = None
        self.scroll_value: int = None

    def set_urls(self, urls: list[str]):
        self._urls = urls

    def get_urls(self):
        return self._urls

    def set_go_to(self, path: str):
        self._go_to = path

    def get_go_to(self):
        return self._go_to
    
    def clear_urls(self):
        self._urls.clear()

    def clear_go_to(self):
        self._go_to = None
