



class Test:

    def one():
        data = {
            "txt": "Hello",
        }
        Test.two(data)
        print(data)

    def two(data: dict):
        data["txt"] = "world"


Test.one()