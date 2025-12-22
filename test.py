class A:
    def __init__(self):
        super().__init__()
        self.test = None


class B(A):
    def __init__(self):
        super().__init__()
        self.new_test = None

a = A()
a.test = 1

b = B()
b.new_test = 2