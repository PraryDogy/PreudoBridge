import subprocess

from PyQt5.QtWidgets import QVBoxLayout


class Utils:
    @staticmethod
    def clear_layout(layout: QVBoxLayout):
        if layout:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
                else:
                    Utils.clear_layout(item.layout())

    @staticmethod
    def copy_path(text: str):
        text_bytes = text.encode('utf-8')
        subprocess.run(['pbcopy'], input=text_bytes, check=True)
        return True