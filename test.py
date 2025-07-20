import os

def get_volume_id(path):
    stat = os.stat(path)
    return (stat.st_dev, )  # st_dev — ID тома


src = "/Users/pupitor9000/Downloads/collections"
a = get_volume_id(src)
print(a)