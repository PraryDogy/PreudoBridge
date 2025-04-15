class A:
    def __init__(self):
        """Привет"""
        super().__init__()

class B(A):
    def __init__(self):
        print(A.__init__.__doc__)
        super().__init__()

B()