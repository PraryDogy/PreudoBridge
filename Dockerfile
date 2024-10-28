# Используйте базовый образ Python
FROM python:3.11

# Устанавливаем необходимые зависимости
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libxkbcommon0 \
    libegl1 \
    libdbus-1-3 \
    libxi6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*


# Установите рабочую директорию
WORKDIR /PseudoBridge

# Скопируйте файл зависимостей (requirements.txt)
COPY requirements2.txt .

# Установите зависимости
RUN pip install --no-cache-dir -r requirements2.txt

# Скопируйте весь проект
COPY . .

# Запустите ваше приложение
CMD ["python3.11", "start.py"]
