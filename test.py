import re


paths = [
    "\"/Users/Loshkarev/Desktop/Архив'",
    "' /Users/Loshkarev/Desktop/Архив   ' ",
    "' /Users/Loshkarev/Desktop/Архив   '  \n",
    "sdfsdfwd"
]

template = r'/([^\'"\s]+)'

for i in paths:
    res = re.search(template, i)
    if res:
        res = res.group(0)
        print(f"\"{res}\"")