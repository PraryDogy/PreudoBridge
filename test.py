from database import ORDER


name = "wefdsf.jpg"
type = ".jpg"
size = 7777
mod = 12312
colors = "some colors"
rating = 5

# order_data = (name, type, size, mod, colors, rating)
# item: dict = {k: v for k, v in zip(ORDER.keys(), order_data)}

item = ("name", "type", "size", "mod", "colors", "rating", "fck")
order = tuple(ORDER.keys())
test = bool(item == order)

if not test:
    print()
    print("grid_standart > LoadFinder > get_items")
    print("итератор item не соответствует ORDER")
    if len(item) > len(order):
        print("Лишний элемент в item")
    else:
        print("Новый элемент в ORDER, добавь его в item")