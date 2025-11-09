# Temiz, sade Python ortamı
FROM python:3.10-slim

# Çalışma dizini
WORKDIR /app

# Gereken dosyaları kopyala
COPY . .

# Gereken kütüphaneleri kur
RUN pip install --no-cache-dir -r requirements.txt

# Uygulamayı başlat
CMD ["python", "main.py"]
