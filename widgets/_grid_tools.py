import sqlalchemy

from database import CACHE, ColumnNames, OrderItem


class GridTools:

    @classmethod
    def load_db_item(cls, conn: sqlalchemy.Connection, order_item: OrderItem):

        select_stmt = sqlalchemy.select(
            CACHE.c.id,
            CACHE.c.img,
            CACHE.c.size,
            CACHE.c.mod,
            CACHE.c.rating
        )

        # Проверка по имени файла
        where_stmt = select_stmt.where(CACHE.c.name == order_item.name)
        res_by_src = conn.execute(where_stmt).mappings().first()

        # Запись найдена
        if res_by_src:

            # даты изменения не совпадают, обновляем запись
            if res_by_src.get(ColumnNames.MOD) != order_item.mod:

                return (
                    res_by_src.get(ColumnNames.ID),
                    res_by_src.get(ColumnNames.RATING)
                )

            # даты изменения совпадают
            return (
                res_by_src.get(ColumnNames.IMG),
                res_by_src.get(ColumnNames.RATING)
            )

        # Запись по имени файла не найдена, возможно файл был переименован,
        # но содержимое файла не менялось
        # Пытаемся найти в БД запись по размеру и дате изменения order_item
        mod_stmt = select_stmt.where(CACHE.c.mod == order_item.mod)
        size_mod_stmt = mod_stmt.where(CACHE.c.size == order_item.size)
        size_mod_res = conn.execute(size_mod_stmt).mappings().first()

        # Если запись найдена, значит файл действительно был переименован
        # возвращаем ID для обновления записи
        if size_mod_res:
            return (
                size_mod_res.get(ColumnNames.ID),
                size_mod_res.get(ColumnNames.RATING)
            )

        # ничего не найдено, значит это будет новая запись и рейтинг 0
        return (None, 0)