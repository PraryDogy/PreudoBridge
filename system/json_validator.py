import json
import pydantic


class JsonValidator:
    def __init__(self, filepath: str, obj: callable, model: pydantic.BaseModel):
        super().__init__()
        self.filepath = filepath
        self.obj = obj
        self.model = model
        
    def get_validated_data(self) -> dict:
        json_data = self.load_json_data(self.filepath) or {}
        obj_data = self.get_obj_data(self.obj)
        errors = []
        
        try:
            self.model(**json_data)
        except pydantic.ValidationError as e:
            print("Некоторые значения в JSON имеют неверные типы и будут заменены значениями по умолчанию.")
            errors = e.errors()

        for err in errors:
            key = err["loc"][0]
            if key in obj_data:
                json_data[key] = obj_data[key]

        return {k: v for k, v in json_data.items() if k in obj_data}
        
    def load_json_data(self, filepath: str):
        with open (filepath, "r", encoding="utf-8") as f:
            data: dict = f.read()
        try:
            data = json.loads(data)
        except json.decoder.JSONDecodeError:
            print("JSON-файл повреждён, пуст или не найден. Будут использованы значения по умолчанию.")
            return None
        return data
    
    def get_obj_data(self, obj: callable):
        return {
            k: getattr(obj, k)
            for k in dir(obj)
            if not k.startswith("__") and not callable(getattr(obj, k))
        }
