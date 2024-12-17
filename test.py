import re

a = "22323 tes44tnew66"

b = re.match(r'^\d+', a)
c = re.search(r'^\d+', a)

print(b)
print(c)