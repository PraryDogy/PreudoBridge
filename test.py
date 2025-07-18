import json
import pydantic


class TestModel(pydantic.BaseModel):
    one: str
    two: int
    tree: list
    four: str


class Test:
    one = "first"
    two = 2
    tree = ["hello", "sex"]
    four = "four"

    @classmethod
    def get_data(cls):
        return {
            k: v
            for k, v in cls.__dict__.items()
            if not k.startswith("__") and not isinstance(v, (classmethod))
        }

    @staticmethod
    def test():
        print(1)

    def meth(self):
        print(1)


class Validator:
    def __init__(self, filepath: str, obj: callable, model: pydantic.BaseModel):
        super().__init__()
        self.filepath = filepath
        self.obj = obj
        self.model = model

    def validate(self):
        json_data = self.json_validate()
        if json_data is None:
            json_data = self.get_obj_data()

        validated = self.keys_validate(json_data)
        if isinstance(validated, pydantic.BaseModel):
            print("валидация пройдена")
        elif isinstance(validated, list):
            print("валидация не пройдена, нужны ключи", validated)

    def json_validate(self):
        with open (self.filepath, "r", encoding="utf-8") as f:
            data: dict = f.read()
        try:
            data = json.loads(data)
        except json.decoder.JSONDecodeError:
            print("json файл поврежден или пуст")
            return None
        return data
    
    def get_obj_data(self):
        return {
            k: getattr(self.obj, k)
            for k in dir(self.obj)
            if not k.startswith("__")
            and
            not callable(getattr(self.obj, k))
        }
    
    def keys_validate(self, json_data: dict):
        try:
            return self.model(**json_data)
        except pydantic.ValidationError as e:
            return [
                x
                for err in e.errors()
                for x in err["loc"]
            ]
    
v = Validator(
    filepath="test.json",
    obj=Test,
    model=TestModel
)

v.validate()


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