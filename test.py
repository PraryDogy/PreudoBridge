ORDER: dict = {
        "name": "Имя",
        "size": "Размер",
        "modify": "Дата",
        "type": "Тип",
        "colors": "Цвета",
        "rating": "Рейтинг",
        }

class JsonData:
    root = "/Volumes"
    ww = 1050
    hh = 700
    ww_im = 700
    hh_im = 500
    sort = list(ORDER.keys())[0]

print(JsonData.sort)