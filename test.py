import json
import pydantic

    
class TestModel(pydantic.BaseModel):
    one: str
    two: int
    tree: list[str]


class Test:
    one = "first"
    two = 2
    tree = ["hello", "sex"]

    @classmethod
    def get_data(cls): ...
    @staticmethod
    def test(): ...
    def meth(self): ...


class Validator:
    def __init__(self, filepath: str, obj: callable, model: pydantic.BaseModel):
        super().__init__()
        self.filepath = filepath
        self.obj = obj
        self.model = model
        
    def get_valid_data(self) -> dict:
        json_data = self.load_json_data(self.filepath) or {}
        obj_data = self.get_obj_data(self.obj)
        errors = []
        
        try:
            self.model(**json_data)
        except pydantic.ValidationError as e:
            errors = e.errors()

        for err in errors:
            key = err["loc"][0]
            if key in obj_data:
                json_data[key] = obj_data[key]

        json_data = {k: v for k, v in json_data.items() if k in obj_data}
        
        return json_data
        
    def load_json_data(self, filepath: str):
        with open (filepath, "r", encoding="utf-8") as f:
            data: dict = f.read()
        try:
            data = json.loads(data)
        except json.decoder.JSONDecodeError:
            # print("json файл поврежден или пуст")
            return None
        return data
    
    def get_obj_data(self, obj: callable):
        return {
            k: getattr(obj, k)
            for k in dir(obj)
            if not k.startswith("__") and not callable(getattr(obj, k))
        }
    
    
v = Validator(filepath="test.json", obj=Test, model=TestModel)
new_json_data = v.get_valid_data()
print(new_json_data)




# json_file = "test.json"

# with open (json_file, "r", encoding="utf-8") as f:
#     data: dict = f.read()

# try:
#     data = json.loads(data)
# except json.decoder.JSONDecodeError:
#     print("json файл поврежден или пуст")
#     data = Test.get_data()

# try:
#     model = TestModel(**data)
# except pydantic.ValidationError as e:
#     print("ошибка валидации json файла")
#     error_keys = [
#         x
#         for err in e.errors()
#         for x in err["loc"]
#     ]


#     default_data = Test.get_data()
#     for k, v in data.items():
#         if k in default_data:
#             default_data[k] = v
#     data = default_data

# with open(json_file, "w", encoding="utf-8") as f:
#     data = json.dump(data, f, ensure_ascii=False, indent=4)