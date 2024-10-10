from math import ceil
from random import randint

test = {i: randint(100, 900) for i in range(1, 18)}
cols = 4
rows = ceil(len(test)/cols)


temp_test = list(test.items())
grid = [
    dict(temp_test[i * cols:(i + 1) * cols])
    for i in range(rows)
]
print(grid)