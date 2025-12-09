import glob
import os

patterns = [
    "/Applications/Adobe Photoshop*/*.app",
    "/Applications/Adobe Photoshop*.app",
    "/Applications/Capture One*/*.app",
    "/Applications/Capture One*.app",
    "/Applications/ImageOptim.app",
    "/System/Applications/Preview.app",
    "/System/Applications/Photos.app",
]

image_apps = []

for pat in patterns:
    for path in glob.glob(pat):
        if path not in image_apps:
            image_apps.append(path)

# сортируем по имени
image_apps.sort(key=os.path.basename)

print(image_apps)
