import os


def get_destination_paths_scandir(src_dir, dest_dir):
    stack = [src_dir]
    file_paths = []

    while stack:
        current_fir = stack.pop()
        for entry in os.scandir(current_fir):
            if entry.is_dir():
                stack.append(entry.path)
            else:
                # Получаем родительскую директорию исходного пути
                # В данном случае это путь к директории, в которой находится исходная папка src_dir
                parent = os.path.dirname(src_dir)
                
                # Получаем относительный путь от исходной директории до текущего файла
                # Этот шаг нужен, чтобы понять, как файл "расположен" относительно папки src_dir
                rel_path = os.path.relpath(entry.path, parent)
                
                # Формируем полный путь для назначения
                # Здесь мы соединяем путь назначения (dest_dir) с относительным путем,
                # полученным в предыдущем шаге, чтобы сохранить структуру директорий
                full_dest = os.path.join(dest_dir, rel_path)
                file_paths.append(full_dest)


    # Возвращаем список путей назначения
    return file_paths



src = "/Users/Loshkarev/Desktop/TEST IMAGES"
dest = "/Users/Loshkarev/Downloads"

paths = get_destination_paths_scandir(src, dest)
# for i in paths:
#     print(i)
