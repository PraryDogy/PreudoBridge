import re

data = ["1te123st", "2hel1lo", "10testnew", "5example3"]

# Сортировка по числу в начале строки
data.sort(key=lambda x: int(re.match(r'^\d+', x).group()))

print(data)