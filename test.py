test = [(1, 2, 3, 4, "ddd"), (5, 6, 7, 8, "wdds")]


k = lambda x: x[3]
a = sorted(test, key=k)

a = reversed(a)

print(a)