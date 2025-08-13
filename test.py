files = [
    "/Volumes/Macintosh HD/Users/Loshkarev/Downloads/0001.tif",
    "/Volumes/Macintosh HD/Users/Loshkarev/Downloads/0002.tif",
    "/Volumes/Macintosh HD/Users/Loshkarev/Downloads/Donors"
]


from system.utils import Utils

file = "/Volumes/Macintosh HD/Users/Loshkarev/Desktop/test.zip"
Utils.zip_items(files, file)