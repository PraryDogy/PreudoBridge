import hashlib
import os

def partial_hash(path: str, chunk: int = 1 << 20) -> tuple[str, str]:
    """
    Вычисляет хеш первых и последних chunk байт файла.
    Возвращает кортеж (hash_start, hash_end) в виде hex-строк.
    """
    size = os.path.getsize(path)
    h_start = hashlib.sha256()
    h_end = hashlib.sha256()

    with open(path, "rb") as f:
        # начало
        h_start.update(f.read(chunk))

        if size > chunk:
            # конец
            f.seek(max(size - chunk, 0))
            h_end.update(f.read(chunk))
        else:
            # если файл меньше чем chunk, используем то же самое
            h_end.update(h_start.digest())

    return h_start.hexdigest(), h_end.hexdigest()


# путь к иконке hashdir, начало хеша, конец хеша
# по сути тебе без разницы, если даже 100 одинаковых файлов в разных папках
# это один и тот же файл, и мы можем загрузить его из бд