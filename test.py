import os


src = "/Volumes/Macintosh HD/Users/Morkowik/Library/Application Support/CloudDocs/session/1.mp3"
root = src.strip(os.sep).split(os.sep)

data = {
    1: "computer",
    2: "hdd",
    **{
        i: "folder"
        for i in range(3, len(root) + 1)
    },
    len(root): "folder" if os.path.isdir(src) else "file"
}

for x, path_item in enumerate(root, start=1):
    item = f"{path_item} : {data.get(x)}"
    print(item)