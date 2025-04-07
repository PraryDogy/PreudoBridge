test = "/Users/Loshkarev/Downloads/005/1231/sdfds/file.txt"

import os

if os.path.isfile(test):
    print("if file")
    test, tail = os.path.split(test)
else:
    print("isdir")

# os.makedirs(test, exist_ok=True)