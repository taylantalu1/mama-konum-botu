import os
import asyncio
from aiogram import Bot, Dispatcher, types

# BOT TOKEN'ını environment variable'dan al
API_TOKEN = os.getenv("BOT_TOKEN")

if not API_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set!")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

@dp.message()
async def echo(message: types.Message):
    await message.answer(f"Mesajın: {message.text}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
