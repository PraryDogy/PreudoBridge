from ast import literal_eval


a = "[1, 2, 3]"
a = "sdfsdf"
a = "1"

b = literal_eval(a)

print(b)
print(type(b))