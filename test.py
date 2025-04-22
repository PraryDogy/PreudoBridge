class Test:
    def __init__(self):
        super().__init__()
        self.value = 0


class Child:
    def __init__(self, test: Test):
        super().__init__()
        self.test = test

    def change_test_value(self):
        self.test.value = 1000


class MainWid:
    def __init__(self):
        super().__init__()
        self.test_item = Test()
        self.child_item = Child(self.test_item)


main = MainWid()
main.child_item.change_test_value()

print(main.test_item.value)