import os


src = "/Applications"

@classmethod
def get_applications():
    for i in os.scandir(src):
        if i.name.endswith((".APP", ".app")):
            continue
        elif i.is_dir():
            for i in os.scandir(i.path):
                if i.name.endswith((".APP", ".app")):
                    print(i.name)