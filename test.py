import subprocess
import os


scpt = "./scripts/copy_files.scpt"
dest = "/Volumes/shares-1/Studio/MIUZ/Photo/Art/Raw/2025/12 - Декабрь/test"
files_dir = "/Volumes/Macintosh HD/Users/Loshkarev/Desktop/DIGEST/test"
files = [i.path for i in os.scandir(files_dir) if not i.name.startswith(".")]



# for i in (files_dir, *files, dest, scpt):
#     print(os.path.exists(i), i)

subprocess.run([
    "osascript",
    scpt,
    dest,
    *files
])
