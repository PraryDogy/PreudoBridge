import os

path = "/Volumes/shares-1/Studio/MIUZ/Photo/Art/FOR RETOUCHERS"

if not os.path.exists(path):
    volumes = [
        i.path
        for i in os.scandir("/Volumes")
    ]
    rel_path = path.strip(os.sep).split(os.sep)
    rel_path = os.sep.join(rel_path[2:])
    for i in volumes:
        new_path = os.path.join(i, rel_path)
        if os.path.exists(new_path):
            print(new_path)