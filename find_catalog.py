import os
import shutil
import subprocess

def read_clipboard():
    try:
        # Чтение буфера обмена (pbpaste для macOS, powershell для Windows)
        result = subprocess.run(
            ["pbpaste"],  # Замените на ["powershell", "-command", "Get-Clipboard"] для Windows
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()
        return result
    except FileNotFoundError:
        print("Команда для чтения буфера обмена не найдена. Убедитесь, что используете правильную команду для своей ОС.")
        exit()

def find_and_copy_files():
    input("Скопируйте путь к папке для поиска и нажмите Enter...")
    src_folder = read_clipboard()
    print("Место поиска:", src_folder)

    print("")
    input("Скопируйте путь к папке назначения и нажмите Enter...")
    dest_folder = read_clipboard()
    print("Место назначения:", dest_folder)

    print("")
    input("Скопируйте список файлов (по одному имени в строке) и нажмите Enter...")
    text = read_clipboard()
    
    src_filenames: list[str] = []

    for i in text.split("\n"):

        filename = i.strip()
        filename, _ = os.path.splitext(filename)

        if filename:
            src_filenames.append(filename)

        
    src_lower_filenames = [i.lower() for i in src_filenames]
    
    if src_lower_filenames:
        print("Поиск")
    
    else:
        print("Нет списка файлов")
        return
        
    for root, _, files in os.walk(src_folder):
        for full_filename in files:

            filename, _ = os.path.splitext(full_filename)
            filename_lower = filename.lower()

            if filename_lower in src_lower_filenames:

                source_path = os.path.join(root, full_filename)
                shutil.copy(source_path, dest_folder)
                print(f"Copied: {full_filename}")

    dest_files_lower = []

    for i in os.listdir(dest_folder):
        filename, _ = os.path.splitext(i)
        filename_lower = filename.lower()
        dest_files_lower.append(filename_lower)

    miss_files = []

    for i in src_filenames:

        filename_lower = filename.lower()
        if filename_lower not in dest_files_lower:
            miss_files.append(str(i))
    
    if miss_files:
        print()
        print("Не найдены файлы:")
        print("\n".join(miss_files))


find_and_copy_files()