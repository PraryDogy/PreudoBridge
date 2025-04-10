import subprocess
import os
from cfg import Static

class Test:
    @classmethod
    def users_path(cls, path: str):
        path = os.sep + path.strip(os.sep)
        users = os.sep + "Users" + os.sep
        volumes = os.sep + "Volumes" + os.sep
        if users in path and path.startswith(volumes):
            splited = path.split(os.sep)[3:]
            return os.path.join(os.sep, *splited)
        return path

src = "Volumes/Macintosh HD/Users/Loshkarev/Downloads"
res = Test.users_path(src)
print(res)