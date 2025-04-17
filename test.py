from database import ORDER_DICT
from widgets._base_widgets import BaseItem


a = BaseItem("/test/file.txt", 0, 0, 0)

for k, v in ORDER_DICT.items():
    if not hasattr(a, k):
        print(k)