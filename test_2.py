class Foo:
    def __init__(self) -> None:
        super().__init__()

    def foo_method(self):
        ...

class Boo:
    def __init__(self) -> None:
        super().__init__()

    def boo_method(self):
        ...

test = Foo()

test: Boo
test.boo_method()