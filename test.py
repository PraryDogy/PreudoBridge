import os

src = "/Users/Morkowik/Desktop/Evgeny/WordsBot/"

src = os.sep + src.strip().strip(os.sep)

print(os.path.exists(src))