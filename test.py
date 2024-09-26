import os

def get_file_size(path: str) -> str:
    size_bytes = os.stat(path).st_size

    size_mb = size_bytes / (1024 * 1024)
    
    if size_mb < 1024:
        return f"{size_mb:.2f}мб"
    else:
        # Иначе возвращаем в гигабайтах
        size_gb = size_mb / 1024
        return f"{size_gb:.2f}гб"
    

file = "/Users/Loshkarev/Downloads/БАБОЧКИ.psd"
a = get_file_size(file)
print(a)