a = {1: 1, 2: 2}
b = list(a.items())
b.insert(1, (123, 123))

c = dict(b)
print(c)