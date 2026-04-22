from dataclasses import dataclass


@dataclass
class Test:
    test: str

    def testing(self):
        print(1)


test = Test("hello")
test.testing()