import os
from cfg import Static


def test():
    for i in os.scandir("/Volumes"):
        if os.path.exists(i.path + Static.APP_SUPPORT_APP):
            return i.path
        
print(test())