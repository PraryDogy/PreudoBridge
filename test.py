import os

src = os.path.dirname(__file__)
count = 0

for root, dir, files in os.walk(src):

    if "/env/" in root:
        continue

    for file in files:

        if file.endswith(".py"):
            p = os.path.join(root, file)
            with open(p, "r") as f:

                data = f.read()
                count += data.count("\n")

print(count)
# 3224