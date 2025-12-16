import os

OUT_DIR = "./test_files"
os.makedirs(OUT_DIR, exist_ok=True)

# ----------------- Дисковые образы -----------------
disk_exts = [
    "dmg",     # macOS disk image
    "iso",     # standard ISO image
    "cdr",     # macOS CD/DVD image
    "img",     # generic disk image
    "vmdk",    # VMware disk
    "vdi",     # VirtualBox disk
    "qcow2",   # QEMU disk
    "vhd",     # Hyper-V disk
    "vhdx",    # Hyper-V newer format
    "sparseimage",
    "sparsebundle",
    "toast",   # Roxio
    "udif",
]

# ----------------- Остальные категории -----------------
# Изображения
image_exts = [
    "jpg", "jpeg", "png", "gif", "bmp", "tiff", "tif",
    "psd", "raw", "cr2", "nef", "arw", "orf", "dng",
    "heic", "webp", "svg", "ai", "eps", "ico", "pdf",
    "xcf", "indd", "kra", "cpt", "tga", "pic", "pcx",
    "djvu"
]

# Документы
doc_exts = [
    "txt", "rtf", "doc", "docx", "odt", "pdf", "xls", "xlsx",
    "ppt", "pptx", "md", "tex", "epub", "mobi", "azw3",
    "csv", "log", "json", "xml", "yaml", "yml"
]

# Архивы
archive_exts = [
    "zip", "rar", "7z", "tar", "gz", "bz2", "xz", "cab", "arj", "lz", "lzma", "sit"
]

# Аудио/видео
media_exts = [
    "mp3", "wav", "flac", "aac", "ogg", "wma", "m4a",
    "mp4", "mov", "avi", "mkv", "flv", "wmv", "webm",
    "m4v", "3gp", "mts", "m2ts", "vob"
]

# Программы/системные
special_exts = [
    "app", "exe", "dll", "so", "pkg", "deb", "rpm",
    "bat", "sh", "command", "folder"
]

# CAD/3D/GIS
cad_exts = [
    "dwg", "dxf", "stl", "obj", "fbx", "3ds", "dae",
    "blend", "gltf", "glb", "max", "skp", "ifc"
]

# ----------------- Объединяем все -----------------
all_exts = image_exts + doc_exts + archive_exts + media_exts + special_exts + cad_exts + disk_exts

# ----------------- Генерация файлов -----------------
for ext in all_exts:
    path = os.path.join(OUT_DIR, f"example.{ext}")
    if ext == "folder":
        os.makedirs(path, exist_ok=True)
    else:
        with open(path, "w") as f:
            f.write("")
