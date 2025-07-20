import os
import shutil

def tkinter_macos_app_cmd(app_dest: str, py_ver: str="3.11"):

    dest = os.path.join(app_dest, "Contents/lib")

    data = {
        "tcl8": f"/Library/Frameworks/Python.framework/Versions/{py_ver}/lib/tcl8",
        "tcl8.6": f"/Library/Frameworks/Python.framework/Versions/{py_ver}/lib/tcl8.6",
        "tk8.6": f"/Library/Frameworks/Python.framework/Versions/{py_ver}/lib/tk8.6"
        }

    for name, src in data.items():
        file_dest = os.path.join(dest, name)
        shutil.copytree(src=src, dst=file_dest, dirs_exist_ok=True)
        
    return True
