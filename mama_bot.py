import logging
import sqlite3
import math
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from keep_alive import keep_alive
import os

API_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# === Veritabanı Ayarları ===
def veritabani_olustur():
    conn = sqlite3.connect("mama_noktalari.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS noktalar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kullanici_id INTEGER,
                enlem REAL,
                boylam REAL,
                aciklama TEXT,
                foto_url TEXT
                )""")
    conn.commit()
    conn.close()

veritabani_olustur()

# === Yardımcı Fonksiyonlar ===
def mesafe_hesapla(lat1, lon1, lat2, lon2):
    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = (math.sin(dLat/2)**2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dLon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# === Menü ===
menu = ReplyKeyboardMarkup(resize_keyboard=True)
menu.add(KeyboardButton("📍 Mama Noktası Ekle"),
         KeyboardButton("🗺️ Yakınımdaki Noktalar"),
         KeyboardButton("📋 Tüm Noktaları Listele"),
         KeyboardButton("ℹ️ Yardım"))

# === Komutlar ===
@dp.message_handler(commands=["start", "yardim"])
async def start_mesaj(message: types.Message):
    await message.answer("🐾 Merhaba! Bu bot sayesinde mama bırakılan noktaları paylaşabilirsin.\n\n"
                         "Kullanım:\n"
                         "📍 Mama Noktası Ekle → Konum, açıklama ve fotoğraf ekle\n"
                         "🗺️ Yakınımdaki Noktalar → En yakın mama alanlarını gör\n"
                         "📋 Tüm Noktaları Listele → Tüm paylaşılan noktaları gör\n\n"
                         "❤️ Hayvan dostlarımız için birlikte daha iyi bir dünya!",
                         reply_markup=menu)

# === Mama Noktası Ekleme ===
@dp.message_handler(lambda message: message.text == "📍 Mama Noktası Ekle")
async def nokta_ekle(message: types.Message):
    await message.answer("Lütfen 📍 konum paylaş (Telegram'da konum gönder tuşunu kullan).")

@dp.message_handler(content_types=["location"])
async def konum_al(message: types.Message):
    user_id = message.from_user.id
    lat = message.location.latitude
    lon = message.location.longitude

    conn = sqlite3.connect("mama_noktalari.db")
    c = conn.cursor()
    c.execute("INSERT INTO noktalar (kullanici_id, enlem, boylam, aciklama, foto_url) VALUES (?, ?, ?, ?, ?)",
              (user_id, lat, lon, '', ''))
    conn.commit()
    conn.close()

    await message.answer("📸 Şimdi bu konuma ait bir fotoğraf gönder (isteğe bağlı).")

@dp.message_handler(content_types=["photo"])
async def foto_ekle(message: types.Message):
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id

    conn = sqlite3.connect("mama_noktalari.db")
    c = conn.cursor()
    c.execute("SELECT id FROM noktalar WHERE kullanici_id=? ORDER BY id DESC LIMIT 1", (user_id,))
    nokta = c.fetchone()
    if nokta:
        c.execute("UPDATE noktalar SET foto_url=? WHERE id=?", (photo_id, nokta[0]))
        conn.commit()
    conn.close()

    await message.answer("📝 Lütfen bu mama noktası hakkında kısa bir açıklama yaz (örneğin: 'Park girişinde, çeşme yanı').")

@dp.message_handler(lambda message: not message.text.startswith("/"))
async def aciklama_al(message: types.Message):
    user_id = message.from_user.id
    aciklama = message.text

    conn = sqlite3.connect("mama_noktalari.db")
    c = conn.cursor()
    c.execute("SELECT id FROM noktalar WHERE kullanici_id=? ORDER BY id DESC LIMIT 1", (user_id,))
    nokta = c.fetchone()
    if nokta:
        c.execute("UPDATE noktalar SET aciklama=? WHERE id=?", (aciklama, nokta[0]))
        conn.commit()
    conn.close()

    await message.answer("✅ Mama noktası kaydedildi! Teşekkürler 💚", reply_markup=menu)

# === Tüm Noktaları Listele ===
@dp.message_handler(lambda message: message.text == "📋 Tüm Noktaları Listele")
async def noktalar_goster(message: types.Message):
    conn = sqlite3.connect("mama_noktalari.db")
    c = conn.cursor()
    c.execute("SELECT enlem, boylam, aciklama, foto_url FROM noktalar")
    noktalar = c.fetchall()
    conn.close()

    if not noktalar:
        await message.answer("Henüz hiç mama noktası eklenmemiş 😿")
        return

    for enlem, boylam, aciklama, foto_id in noktalar:
        konum_linki = f"https://www.google.com/maps?q={enlem},{boylam}"
        if foto_id:
            await message.answer_photo(photo= foto_id,
                                       caption=f"📍 {konum_linki}\n📝 {aciklama}")
        else:
            await message.answer(f"📍 {konum_linki}\n📝 {aciklama}")

# === Yakınımdaki Noktalar ===
@dp.message_handler(lambda message: message.text == "🗺️ Yakınımdaki Noktalar")
async def yakin_nokta(message: types.Message):
    await message.answer("📍 Lütfen bulunduğun konumu paylaş (Telegram'da konum gönder tuşunu kullan).")

@dp.message_handler(content_types=["location"])
async def konum_bul(message: types.Message):
    user_lat = message.location.latitude
    user_lon = message.location.longitude

    conn = sqlite3.connect("mama_noktalari.db")
    c = conn.cursor()
    c.execute("SELECT enlem, boylam, aciklama, foto_url FROM noktalar")
    noktalar = c.fetchall()
    conn.close()

    if not noktalar:
        await message.answer("Henüz kayıtlı mama noktası yok 😿")
        return

    uzakliklar = []
    for enlem, boylam, aciklama, foto in noktalar:
        d = mesafe_hesapla(user_lat, user_lon, enlem, boylam)
        uzakliklar.append((d, enlem, boylam, aciklama, foto))

    yakinlar = sorted(uzakliklar)[:5]
    for d, enlem, boylam, aciklama, foto in yakinlar:
        link = f"https://www.google.com/maps?q={enlem},{boylam}"
        if foto:
            await message.answer_photo(foto, caption=f"📍 {link}\n📝 {aciklama}\n📏 Uzaklık: {d:.2f} km")
        else:
            await message.answer(f"📍 {link}\n📝 {aciklama}\n📏 Uzaklık: {d:.2f} km")

# === Botu Başlat ===
if __name__ == '__main__':
    keep_alive()
    executor.start_polling(dp, skip_updates=True)
