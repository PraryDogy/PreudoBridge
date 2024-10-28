# Используйте базовый образ Python
FROM python:3.11

RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Установите рабочую директорию
WORKDIR /PseudoBridge

# Скопируйте файл зависимостей (requirements.txt)
COPY requirements.txt .

# Установите зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Скопируйте весь проект
COPY . .

# Запустите ваше приложение
CMD ["python3.11", "start.py"]
