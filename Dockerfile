FROM python:3.11

RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libxkbcommon0 \
    libegl1 \
    libdbus-1-3 \
    libxi6 \
    libxrender1 \
    libx11-xcb1 \
    libxcb-xinerama0 \
    libxrandr2 \
    libxss1 \
    libglu1-mesa \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /PseudoBridge

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python3.11", "start.py"]
