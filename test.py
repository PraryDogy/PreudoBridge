data = [f"widget {i}" for i in range(0, 4)]
cols = 3
rows = len(data) // cols

# for row in range(rows):
#     for col in range(cols):
#         index = row * cols + col
#         print(row, col, data[index])

for index, item in enumerate(data):
    row, col = divmod(index, cols)
    print(row, col, item)