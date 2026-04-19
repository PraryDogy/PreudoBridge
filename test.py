class Foo:
    def __init__(self):
        super().__init__()
        self.test: str


foo = Foo()
foo.test = None


print(foo.test)

