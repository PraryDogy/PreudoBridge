ORDER: dict = {
        "name": {"text": "Имя", "index": 0},
        "size": {"text": "Размер", "index": 1},
        "modify": {"text": "Дата", "index": 2},
        "type": {"text": "Тип", "index": 3},
        "colors": {"text": "Цвета", "index": 4},
        "rating": {"text": "Рейтинг", "index": 5},
        **{
            str(i): {"text": str(i), "index": i}
            for i in range(6, 14)
        }
        }

sort = list(ORDER.keys())[0]

print(sort)