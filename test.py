import os
import json

data = []
for i in os.scandir("./uti_icons/uti_icons"):
    data.append(i.name)
# data = tuple(data)

# print(data)

with open("./uti_icons/uti_icons.json", "w") as file:
    json.dump(data, file, indent=1)