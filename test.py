from typing import Dict, Callable


def test():
    print("test")

def best():
    print("best")


tester: Dict[int, Callable] = {
    1: test,
    2: best
}

a = tester.get(1)

if a is not None:
    a()