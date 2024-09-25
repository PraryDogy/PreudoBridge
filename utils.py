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