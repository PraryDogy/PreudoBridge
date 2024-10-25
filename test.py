import os


src = "/Users/Loshkarev/Desktop/Снимок экрана 2024-10-25 в 11.09.44.jpg/"
src = src.strip().strip(os.sep)
name = os.path.basename(src)
type = os.path.splitext(name)[-1]
print(type)