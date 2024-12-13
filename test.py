data = ["1 Solo", "2 Redmi", "11 Test"]
sorted_data = sorted(data, key=lambda x: int(x.split()[0]))
print(sorted_data)
