import os
import json
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Location
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes, CallbackQueryHandler
from pymongo import MongoClient
import folium
from io import BytesIO

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# MongoDB Bağlantısı
client = MongoClient(MONGODB_URI)
db = client["sokak_hayvan_mama"]
locations_collection = db["locations"]
users_collection = db["users"]

# Conversation States
LOCATION, DESCRIPTION, TIME = range(3)
EDIT_CHOICE = range(1)

# Admin kontrol
def is_admin(user_id):
    return user_id == ADMIN_ID

# Konum ekleme
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📍 Konum Ekle", callback_data="add_location")],
        [InlineKeyboardButton("🗺️ Haritayı Gör", callback_data="view_map")],
        [InlineKeyboardButton("📋 Tüm Noktaları Listele", callback_data="list_locations")],
        [InlineKeyboardButton("🗑️ Benim Noktalarım", callback_data="my_locations")]
    ]
    
    if is_admin(update.effective_user.id):
        keyboard.append([InlineKeyboardButton("⚙️ Admin Paneli", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🐾 Sokak Hayvanı Mama Paylaşım Noktası Botuna Hoş Geldiniz!\n\n"
        "Burada mama bırakılacak noktaları paylaşabilirsiniz.",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "add_location":
        await query.edit_message_text(
            "📍 Konumunuzu paylaşın (Telegram'ın konum özelliğini kullanın):"
        )
        context.user_data["adding_location"] = True
        return LOCATION
    
    elif query.data == "view_map":
        await generate_and_send_map(query, context)
    
    elif query.data == "list_locations":
        await list_all_locations(query)
    
    elif query.data == "my_locations":
        await my_locations(query, update.effective_user.id)
    
    elif query.data == "admin_panel":
        if is_admin(update.effective_user.id):
            await admin_panel(query)
    
    elif query.data.startswith("delete_"):
        location_id = query.data.split("_")[1]
        await delete_location(query, location_id, update.effective_user.id)

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("adding_location"):
        return
    
    location = update.message.location
    context.user_data["latitude"] = location.latitude
    context.user_data["longitude"] = location.longitude
    
    await update.message.reply_text("✅ Konum alındı!\n\nŞimdi açıklama yazın (örn: 'Kapı önü', 'Park bahçesi'):")
    return DESCRIPTION

async def handle_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = update.message.text
    await update.message.reply_text("📅 Mama bırakılacak zaman/gün yazın (örn: 'Her gün saat 18:00', 'Cumartesi sabahları'):")
    return TIME

async def handle_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["time"] = update.message.text
    
    # Veritabanına kaydet
    location_doc = {
        "user_id": update.effective_user.id,
        "username": update.effective_user.username or "Anonim",
        "latitude": context.user_data["latitude"],
        "longitude": context.user_data["longitude"],
        "description": context.user_data["description"],
        "time": context.user_data["time"],
        "created_at": datetime.now(),
        "approved": not is_admin(ADMIN_ID)  # Admin varsa onay bekle
    }
    
    result = locations_collection.insert_one(location_doc)
    
    if is_admin(ADMIN_ID):
        await update.message.reply_text(
            "⏳ Konumunuz admin onayı beklemektedir.\n\n"
            f"📍 Açıklama: {context.user_data['description']}\n"
            f"⏰ Zaman: {context.user_data['time']}"
        )
    else:
        await update.message.reply_text(
            "✅ Konum başarıyla eklendi!\n\n"
            f"📍 Açıklama: {context.user_data['description']}\n"
            f"⏰ Zaman: {context.user_data['time']}"
        )
    
    context.user_data.clear()
    return ConversationHandler.END

async def generate_and_send_map(query, context):
    locations = list(locations_collection.find({"approved": True}))
    
    if not locations:
        await query.edit_message_text("📍 Henüz onaylanmış konum yok.")
        return
    
    # Harita oluştur
    center_lat = sum(loc["latitude"] for loc in locations) / len(locations)
    center_lon = sum(loc["longitude"] for loc in locations) / len(locations)
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=13)
    
    for loc in locations:
        popup_text = f"""
        <b>{loc['description']}</b><br>
        ⏰ {loc['time']}<br>
        👤 {loc['username']}
        """
        folium.Marker(
            location=[loc["latitude"], loc["longitude"]],
            popup=folium.Popup(popup_text, max_width=250),
            icon=folium.Icon(color="orange", icon="paw")
        ).add_to(m)
    
    # Haritayı dosyaya kaydet
    map_path = "/tmp/mama_map.html"
    m.save(map_path)
    
    await query.edit_message_text("🗺️ Harita oluşturuluyor...")
    
    with open(map_path, "rb") as f:
        await query.message.reply_document(f, filename="mama_haritasi.html")

async def list_all_locations(query):
    locations = list(locations_collection.find({"approved": True}).sort("created_at", -1))
    
    if not locations:
        await query.edit_message_text("📍 Henüz konum yok.")
        return
    
    text = "📋 **Tüm Mama Noktaları:**\n\n"
    for i, loc in enumerate(locations, 1):
        text += f"{i}. 📍 {loc['description']}\n"
        text += f"   ⏰ {loc['time']}\n"
        text += f"   👤 @{loc['username']}\n\n"
    
    await query.edit_message_text(text, parse_mode="Markdown")

async def my_locations(query, user_id):
    locations = list(locations_collection.find({"user_id": user_id}))
    
    if not locations:
        await query.edit_message_text("Henüz bir konum eklemediniz.")
        return
    
    text = "🔍 **Sizin Eklediğiniz Noktalar:**\n\n"
    keyboard = []
    
    for loc in locations:
        status = "✅" if loc.get("approved") else "⏳"
        text += f"{status} {loc['description']} - {loc['time']}\n"
        keyboard.append([InlineKeyboardButton(f"🗑️ Sil: {loc['description']}", callback_data=f"delete_{loc['_id']}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def delete_location(query, location_id, user_id):
    from bson.objectid import ObjectId
    
    location = locations_collection.find_one({"_id": ObjectId(location_id)})
    
    if location and location["user_id"] == user_id:
        locations_collection.delete_one({"_id": ObjectId(location_id)})
        await query.edit_message_text("✅ Konum silindi!")
    else:
        await query.edit_message_text("❌ Bu işlem için yetkiniz yok.")

async def admin_panel(query):
    pending = list(locations_collection.find({"approved": False}))
    
    text = f"⚙️ **Admin Paneli**\n\n"
    text += f"⏳ Onay Bekleyen: {len(pending)}\n"
    text += f"✅ Onaylı: {locations_collection.count_documents({'approved': True})}\n\n"
    
    keyboard = [[InlineKeyboardButton("📋 Onay Bekleyenleri Gör", callback_data="pending_approvals")]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def pending_approvals(query):
    pending = list(locations_collection.find({"approved": False}))
    
    if not pending:
        await query.edit_message_text("✅ Tüm noktalar onaylanmış!")
        return
    
    keyboard = []
    for loc in pending:
        keyboard.append([
            InlineKeyboardButton(f"✅ Onayla: {loc['description']}", callback_data=f"approve_{loc['_id']}"),
            InlineKeyboardButton("❌", callback_data=f"reject_{loc['_id']}")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("⏳ **Onay Bekleyen Noktalar:**", reply_markup=reply_markup)

async def main():
    app = Application.builder().token(TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LOCATION: [MessageHandler(filters.LOCATION, handle_location)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_description)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_time)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    app.add_handler(conv_handler)
    
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
