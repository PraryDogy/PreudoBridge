from system.items import ThumbProperties


class Foo(ThumbProperties):
    def __init__(self):
        super().__init__()


a = Foo()
print(a.src)