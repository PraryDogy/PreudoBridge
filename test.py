counter = 23
cell_to_wid = [i for i in range(0, counter)]
col_count = 5

col = len(cell_to_wid) % col_count
row = len(cell_to_wid) // col_count

print(row, col)

print(len(cell_to_wid))