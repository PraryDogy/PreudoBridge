d = {1: 1, 2: 2, 3: 3}



old_key = 2
new_key = 666
new_value = "q32"


v = {
    (new_key if k == old_key else k): (new_value if k == old_key else v)
    for k, v in d.items()
}


print(v)