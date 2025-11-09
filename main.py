import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command
from flask import Flask, jsonify
import os

# -------------------------------
# Config
# -------------------------------
try:
    from config import BOT_TOKEN
except ImportError:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN ayarlanmadı! config.py veya Render env vars kullanın.")

# -------------------------------
# Telegram Bot
# -------------------------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("Merhaba! Konum botuna hoş geldiniz.")

@dp.message(content_types=types.ContentType.LOCATION)
async def location_handler(message: Message):
    lat = message.location.latitude
    lon = message.location.longitude
    print(f"Yeni konum alındı: {lat}, {lon}")
    await message.answer(f"Konumunuz alındı: {lat}, {lon}")

# -------------------------------
# Flask API
# -------------------------------
app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

# -------------------------------
# Run
# -------------------------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
