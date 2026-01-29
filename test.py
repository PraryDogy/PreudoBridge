from pathlib import Path


src = "/Users/Loshkarev/Desktop"
dst = "/Users/Loshkarev/Downloads"
file = '/Users/Loshkarev/Desktop/test/Колье каркасное.jpg'


src = Path(src)
dst = Path(dst)
file = Path(file)

res = file.relative_to(src)
res = dst.joinpath(res)

print(res)