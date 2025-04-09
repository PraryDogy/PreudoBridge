class SubClass:
    def __init__(self, main_dir: str):
        super().__init__()
        self.main_dir = main_dir


class Parent:
    def __init__(self):
        super().__init__()
        self.main_dir = 1

    def set_value(self, value: int):
        self.main_dir = value


first = Parent()
second = SubClass(main_dir=first.main_dir)

print(second.main_dir)
first.set_value(value=666)
print(second.main_dir)