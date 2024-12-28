a = {1: 1, 2: 2, 3: 3}



for x, (name, value) in enumerate(a.items(), start=3):


    print(x, name, value)


print(len(a))