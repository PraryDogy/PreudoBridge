import os
dow = os.path.expanduser("~/Downloads")
for x, i in enumerate(os.scandir(dow), start=1):
    print(x)