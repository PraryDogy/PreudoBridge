test = {
    (1, 2, 3): 0,
    (1, 5, 1): 0,
    (3, 5, 0): 0,
    }


test = dict(sorted(test.items(), key=lambda item: item[0][-1]))
print(test)