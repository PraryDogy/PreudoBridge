"""
Python 3.11
"""

import os


class PyQt5App:

    @classmethod
    def set_plugin_path(cls) -> bool:
        #lib folder appears when we pack this project to .app with py2app
        if os.path.exists("lib"): 
            plugin_path = "lib/python3.11/PyQt5/Qt5/plugins"
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugin_path
            return True
        else:
            return False


PyQt5App.set_plugin_path()