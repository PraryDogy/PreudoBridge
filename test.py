class Parent:
    def __init__(self):
        super().__init__()
        self.row: int = 0


class Boo(Parent):
    def __init__(self):
        super().__init__()

    def test(self):
        self.row = 1