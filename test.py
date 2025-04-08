import os


def get_new_paths(src_dir: str, dest: str):
    stack = [src_dir]
    new_paths: list[tuple[str, str]] = []

    src_dir = os.sep + src_dir.strip(os.sep)
    dest = os.sep + dest.strip(os.sep)

    # получем директорию на 1 выше, чем исходная папка с файлами,
    # чтобы извлекать относительный путь к файлу,
    # чтобы потом создавать новый путь к файлу:
    # место назначения + относительный путь к файлу
    parent = os.path.dirname(src_dir)

    while stack:
        current_dir = stack.pop()

        for dir_entry in os.scandir(current_dir):
            if dir_entry.is_dir():
                stack.append(dir_entry.path)
            else:
                rel_path = dir_entry.path.split(parent)[-1]
                new_path = dest + rel_path
                new_paths.append((dir_entry.path, new_path))

    # for i in new_paths:
    #     print(i)


src_dir = "/Users/Loshkarev/Desktop/TEST IMAGES"
dest = "/Users/Loshkarev/Downloads"
get_new_paths(src_dir, dest)