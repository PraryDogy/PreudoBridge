abc = [i for i in range(0, 59)]
step = 10
test = [
    abc[i:i+step]
    for i in range(0, len(abc), step)
]

for i in test:
    print(i)