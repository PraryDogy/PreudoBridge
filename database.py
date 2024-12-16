import os

import sqlalchemy
from sqlalchemy.exc import OperationalError

from cfg import Static, JsonData
from utils import Utils

METADATA = sqlalchemy.MetaData()

CACHE = sqlalchemy.Table(
    "cache", METADATA,
    # Определяем таблицу "cache" с её метаданными.
    # Комментарии колонок используются только для сортировки.
    # Где есть комментарий — сортировка возможна.
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("src", sqlalchemy.Text, unique=True),
    sqlalchemy.Column("hash_path", sqlalchemy.Text),
    sqlalchemy.Column("root", sqlalchemy.Text),
    sqlalchemy.Column("catalog", sqlalchemy.Text, nullable=False),
    sqlalchemy.Column("name", sqlalchemy.Text, comment="Имя"),
    sqlalchemy.Column("type_", sqlalchemy.Text, comment="Тип"),
    sqlalchemy.Column("size", sqlalchemy.Integer, comment="Размер"),
    sqlalchemy.Column("mod", sqlalchemy.Integer, comment="Дата изменения"),
    sqlalchemy.Column("resol", sqlalchemy.Integer),
    sqlalchemy.Column("colors", sqlalchemy.Text, nullable=False, comment="Цвета"),
    sqlalchemy.Column("rating", sqlalchemy.Integer, nullable=False, comment="Рейтинг")
)

# ORDER создаётся как словарь, где ключ — это имя колонки с комментарием,
# а значение — словарь с текстом комментария и индексом колонки.
ORDER: dict[str, dict[str, int]] = {
    clmn.name: {"text": clmn.comment}  # Включаем только колонки с комментариями.
    for ind, clmn in enumerate(CACHE.columns)  # Перебираем все колонки в CACHE.
    if clmn.comment  # Фильтруем колонки с комментариями.
}

# Список всех колонок из CACHE, начиная со второй (пропускаем "id").
CACHE_CLMNS = [
    i.name  # Извлекаем имена колонок.
    for i in CACHE.columns  # Перебираем все колонки.
][1:]  # Пропускаем первый элемент (id).


class OrderItem:
    def __init__(self, src: str, size: int, mod: int, colors: str, rating: int):
        super().__init__()
        self.src: str = src
        self.size: int = size
        self.mod: int = mod
        self.colors: str = colors
        self.rating: int = rating

        # Извлечение имени файла из пути (например, "path/to/file.txt" -> "file.txt")
        self.name: str = os.path.split(self.src)[-1]
            
        # Проверка: если путь ведёт к директории, то задаём тип FOLDER_TYPE.
        # Иначе определяем тип по расширению файла (например, ".txt").    
        if os.path.isdir(src):
            self.type_ = Static.FOLDER_TYPE
        else:
            self.type_ = os.path.splitext(self.src)[-1]

    @classmethod
    def order_items(cls, order_items: list["OrderItem"]) -> list["OrderItem"]:
        
        # Получаем список ключей сортировки из ORDER.
        order = list(ORDER.keys())

        # Проверяем, есть ли заданный метод сортировки в списке доступных.
        if JsonData.sort not in order:
            print("database > OrderItem > order_items")
            print("Такой сортировки не существует:", JsonData.sort)
            print("Применяю сортировку из ORDER:", order[0])
            JsonData.sort = order[0]

        # Если выбранная сортировка — по длине поля colors.
        if JsonData.sort == "colors":

            # Ключ сортировки — длина строки атрибута colors.
            key = lambda x: len(getattr(x, JsonData.sort))

        # elif JsonData.sort == "name":

            # # Используем метод sort_key для корректной обработки имён.
            # key = lambda x: cls.sort_key(
            #     x=getattr(x, JsonData.sort)
            # )

        # Для всех других типов сортировки (например, по числовым атрибутам).
        else:

            # Сортируем по значению соответствующего атрибута объекта.
            key = lambda x: getattr(x, JsonData.sort)

        # Учитываем параметр реверса сортировки.
        rev = JsonData.reversed

        return sorted(order_items, key=key, reverse=rev)

    @classmethod
    def sort_key(cls, x: str):
        # Разбиваем строку на части (сначала числа, потом текст).
        # Если часть — число, то преобразуем в int, иначе задаём бесконечность.
        parts = x.split()
        return int(parts[0]) if parts[0].isdigit() else float('inf')


class Dbase:
    # Это класс для работы с базой данных
    engine: sqlalchemy.Engine = None  # Инициализация переменной для движка SQLAlchemy.

    @classmethod
    def init_db(cls):
        # Инициализация базы данных, создание соединения и таблиц.
        cls.engine = sqlalchemy.create_engine(
            f"sqlite:///{Static.DB_FILE}",  # Используется SQLite база с файлом из Static.DB_FILE.
            echo=False,  # Отключение логирования SQL запросов.
            connect_args={
                "check_same_thread": False,  # Разрешение на использование соединений в разных потоках.
                "timeout": 15  # Тайм-аут для подключения (15 секунд).
            }
        )
        METADATA.create_all(cls.engine)  # Создание всех таблиц по метаданным.
        cls.toggle_wal(False)  # Отключаем WAL (write-ahead logging).
        cls.check_tables()  # Проверка таблиц в базе.
        cls.check_values()  # Проверка значений в базе.

    @classmethod
    def toggle_wal(cls, value: bool):
        # Переключение режима журнала (WAL или DELETE).
        with cls.engine.connect() as conn:
            if value:
                conn.execute(sqlalchemy.text("PRAGMA journal_mode=WAL"))  # Включаем WAL.
            else:
                conn.execute(sqlalchemy.text("PRAGMA journal_mode=DELETE"))  # Включаем обычный режим.

    @classmethod
    def clear_db(cls):
        # Очищение базы данных, удаление данных из таблицы CACHE.
        conn = cls.engine.connect()

        try:
            q_del_cache = sqlalchemy.delete(CACHE)  # Подготовка запроса на удаление всех данных из таблицы CACHE.
            conn.execute(q_del_cache)  # Выполнение запроса.

        except OperationalError as e:
            # Обработка ошибок, если возникнут проблемы с удалением.
            Utils.print_error(cls, e)
            conn.rollback()  # Откат транзакции.
            return False

        conn.commit()  # Подтверждение изменений.
        conn.execute(sqlalchemy.text("VACUUM"))  # Освобождение неиспользуемого пространства.
        conn.close()  # Закрытие соединения.

        return True

    @classmethod
    def check_tables(cls):
        # Проверка наличия необходимых таблиц в базе данных.
        inspector = sqlalchemy.inspect(cls.engine)  # Создаём инспектора для проверки базы.

        TABLES = [CACHE]  # Список всех нужных таблиц.

        db_tables = inspector.get_table_names()  # Получаем список таблиц из базы данных.
        res: bool = (list(i.name for i in TABLES) == db_tables)  # Сравниваем с необходимыми таблицами.

        if not res:
            # Если таблицы не соответствуют, создаём новую базу данных.
            print("Не соответствие таблиц, создаю новую дб")
            os.remove(Static.DB_FILE)  # Удаляем старую базу.
            cls.init_db()  # Инициализируем новую базу.
            return

        for table in TABLES:
            # Проверка соответствия колонок в таблицах.
            clmns = list(clmn.name for clmn in table.columns)  # Получаем список нужных колонок.
            db_clmns = list(clmn.get("name") for clmn in inspector.get_columns(table.name))  # Колонки из базы.
            res = bool(db_clmns == clmns)  # Сравниваем.

            if not res:
                # Если колонки не соответствуют, создаём новую базу данных.
                print(f"Не соответствие колонок в {table.name}, создаю новую дб")
                os.remove(Static.DB_FILE)  # Удаляем старую базу.
                cls.init_db()  # Инициализируем новую базу.
                break

    @classmethod
    def check_values(cls):
        # Проверка, что все колонки правильно учитываются при создании новой записи в базе.
        values = cls.get_cache_values(*["" for i in range(0, 7)])  # Генерация пустых значений для проверки.
        assert list(values.keys()) == CACHE_CLMNS, "проверь get_cache_values"  # Проверяем соответствие колонок.

    @classmethod
    def get_cache_values(
        cls, src, hash_path, name, type_, size, mod, resol
    ) -> dict[str, str]:
        # Возвращает словарь значений для новой записи в базе данных.
        return {
            "src": src,  # Путь к файлу.
            "hash_path": hash_path,  # Хэш пути.
            "root": os.path.dirname(src),  # Корневая директория файла.
            "catalog": "",  # Каталог (пока пустой).
            "name": name,  # Имя файла.
            "type_": type_,  # Тип файла.
            "size": size,  # Размер файла.
            "mod": mod,  # Дата изменения файла.
            "resol": resol,  # Разрешение (если применимо).
            "colors": "",  # Цвета (пока пустые).
            "rating": 0  # Рейтинг (по умолчанию 0).
        }
