src = "/Volumes/Macintosh HD/Users/evlosh/Downloads"

import os

short_src = os.sep + os.sep.join(src.split(os.sep)[3:])

print(short_src)