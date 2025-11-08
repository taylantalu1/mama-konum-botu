import asyncio
from aiogram import Bot, Dispatcher, types
from config import BOT_TOKEN  # config.py’den alıyoruz

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN config.py dosyasında ayarlanmamış!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message()
async def echo(message: types.Message):
    await message.answer(f"Mesajın: {message.text}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
