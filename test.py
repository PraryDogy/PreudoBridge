test_list = ["1" for i in range(0, 100)]
search_text = "123"

for i in test_list:
    if search_text in i or i in search_text:
        print("!!")