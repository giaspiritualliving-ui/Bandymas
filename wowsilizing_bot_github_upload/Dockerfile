# Базовый образ с Python 3.11
FROM python:3.11-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем yt-dlp
RUN wget https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -O /usr/local/bin/yt-dlp \
    && chmod a+rx /usr/local/bin/yt-dlp

# Создаем рабочую директорию
WORKDIR /app

# Копируем requirements.txt и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код бота
COPY . .

# Создаем необходимые директории
RUN mkdir -p temp data logs data/cache

# Переменные окружения (будут переопределены в Railway)
ENV BOT_TOKEN=""
ENV PREMIUM_USERNAME="WowFUX"
ENV LOG_LEVEL="INFO"

# Запускаем бота
CMD ["python", "bot.py"]
