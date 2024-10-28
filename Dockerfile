# Используйте базовый образ Python
FROM python:3.11

# Установите рабочую директорию
WORKDIR /PseudoBridge

# Скопируйте файл зависимостей (requirements.txt)
COPY requirements.txt .

# Установите зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Скопируйте весь проект
COPY . .
