import os
from utils import Utils

src = "/Users/Loshkarev/Downloads/R01-MLN1265-450-0002.png"

if src.startswith(os.path.expanduser("~")):
    src = Utils.get_system_volume() + src

print(src)