import hashlib
import os

# Функция для вычисления частичного хеша файла.
# Хешируются первые и последние 10 МБ файла (или весь файл, если он меньше 10 МБ).
def get_partial_hash(file_path):
    # Устанавливаем размер чанка для хеширования (10 МБ).
    chunk_size = 10 * 1024 * 1024  
    # Создаём объект SHA-256 для вычисления хеша.
    hash_func = hashlib.sha256()

    # Определяем размер файла.
    file_size = os.path.getsize(file_path)
    
    with open(file_path, 'rb') as f:
        # Если файл меньше или равен chunk_size, читаем и хешируем его целиком.
        if file_size <= chunk_size:
            hash_func.update(f.read())
        else:
            # Читаем и хешируем первые chunk_size байт файла.
            hash_func.update(f.read(chunk_size))
            # Переходим к последним chunk_size байтам файла и хешируем их.
            f.seek(-chunk_size, os.SEEK_END)
            hash_func.update(f.read(chunk_size))
    
    # Возвращаем итоговый хеш в шестнадцатеричном формате.
    return hash_func.hexdigest()

# Указываем путь к файлу.
file_path = "/Users/Loshkarev/Desktop/1595516162133779072.jpg"
# Вычисляем частичный хеш.
hash_value = get_partial_hash(file_path)
# Выводим результат.
print(f"Partial Hash: {hash_value}")
