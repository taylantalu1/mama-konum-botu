import os
import json
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes, CallbackQueryHandler
import folium
from pathlib import Path

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# JSON Dosyası
DATA_FILE = "locations.json"
APPROVED_FILE = "approved_locations.json"

def load_data(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_data(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

# Conversation States
LOCATION, DESCRIPTION, TIME = range(3)

# Admin kontrol
def is_admin(user_id):
    return user_id == ADMIN_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📍 Konum Ekle", callback_data="add_location")],
        [InlineKeyboardButton("🗺️ Haritayı Gör", callback_data="view_map")],
        [InlineKeyboardButton("📋 Tüm Noktaları Listele", callback_data="list_locations")],
        [InlineKeyboardButton("🔍 Benim Noktalarım", callback_data="my_locations")]
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
    
    elif query.data == "view_map":
        await generate_and_send_map(query, context)
    
    elif query.data == "list_locations":
        await list_all_locations(query)
    
    elif query.data == "my_locations":
        await my_locations(query, update.effective_user.id)
    
    elif query.data == "admin_panel":
        if is_admin(update.effective_user.id):
            await admin_panel(query)
    
    elif query.data == "pending_approvals":
        if is_admin(update.effective_user.id):
            await pending_approvals(query)
    
    elif query.data.startswith("delete_"):
        idx = int(query.data.split("_")[1])
        await delete_location(query, idx, update.effective_user.id)
    
    elif query.data.startswith("approve_"):
        idx = int(query.data.split("_")[1])
        await approve_location(query, idx)
    
    elif query.data.startswith("reject_"):
        idx = int(query.data.split("_")[1])
        await reject_location(query, idx)

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
    
    # JSON'a kaydet
    locations = load_data(DATA_FILE)
    
    location_doc = {
        "user_id": update.effective_user.id,
        "username": update.effective_user.username or "Anonim",
        "latitude": context.user_data["latitude"],
        "longitude": context.user_data["longitude"],
        "description": context.user_data["description"],
        "time": context.user_data["time"],
        "created_at": datetime.now().isoformat(),
        "approved": not is_admin(ADMIN_ID)
    }
    
    locations.append(location_doc)
    save_data(DATA_FILE, locations)
    
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
    locations = load_data(DATA_FILE)
    approved = [loc for loc in locations if loc.get("approved", False)]
    
    if not approved:
        await query.edit_message_text("📍 Henüz onaylanmış konum yok.")
        return
    
    # Harita oluştur
    center_lat = sum(loc["latitude"] for loc in approved) / len(approved)
    center_lon = sum(loc["longitude"] for loc in approved) / len(approved)
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=13)
    
    for loc in approved:
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
    map_path = "mama_map.html"
    m.save(map_path)
    
    await query.edit_message_text("🗺️ Harita gönderiliyor...")
    
    with open(map_path, "rb") as f:
        await query.message.reply_document(f, filename="mama_haritasi.html")

async def list_all_locations(query):
    locations = load_data(DATA_FILE)
    approved = [loc for loc in locations if loc.get("approved", False)]
    
    if not approved:
        await query.edit_message_text("📍 Henüz konum yok.")
        return
    
    text = "📋 **Tüm Mama Noktaları:**\n\n"
    for i, loc in enumerate(approved, 1):
        text += f"{i}. 📍 {loc['description']}\n"
        text += f"   ⏰ {loc['time']}\n"
        text += f"   👤 @{loc['username']}\n\n"
    
    await query.edit_message_text(text, parse_mode="Markdown")

async def my_locations(query, user_id):
    locations = load_data(DATA_FILE)
    my_locs = [loc for loc in locations if loc["user_id"] == user_id]
    
    if not my_locs:
        await query.edit_message_text("Henüz bir konum eklemediniz.")
        return
    
    text = "🔍 **Sizin Eklediğiniz Noktalar:**\n\n"
    keyboard = []
    
    for idx, loc in enumerate(locations):
        if loc["user_id"] == user_id:
            status = "✅" if loc.get("approved") else "⏳"
            text += f"{status} {loc['description']} - {loc['time']}\n"
            keyboard.append([InlineKeyboardButton(f"🗑️ Sil: {loc['description']}", callback_data=f"delete_{idx}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def delete_location(query, idx, user_id):
    locations = load_data(DATA_FILE)
    
    if idx < len(locations) and locations[idx]["user_id"] == user_id:
        locations.pop(idx)
        save_data(DATA_FILE, locations)
        await query.edit_message_text("✅ Konum silindi!")
    else:
        await query.edit_message_text("❌ Bu işlem için yetkiniz yok.")

async def admin_panel(query):
    locations = load_data(DATA_FILE)
    pending = [loc for loc in locations if not loc.get("approved", False)]
    approved = [loc for loc in locations if loc.get("approved", False)]
    
    text = f"⚙️ **Admin Paneli**\n\n"
    text += f"⏳ Onay Bekleyen: {len(pending)}\n"
    text += f"✅ Onaylı: {len(approved)}\n\n"
    
    keyboard = [[InlineKeyboardButton("📋 Onay Bekleyenleri Gör", callback_data="pending_approvals")]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def pending_approvals(query):
    locations = load_data(DATA_FILE)
    pending = [(idx, loc) for idx, loc in enumerate(locations) if not loc.get("approved", False)]
    
    if not pending:
        await query.edit_message_text("✅ Tüm noktalar onaylanmış!")
        return
    
    keyboard = []
    text = "⏳ **Onay Bekleyen Noktalar:**\n\n"
    
    for idx, loc in pending:
        text += f"📍 {loc['description']} - {loc['time']}\n👤 @{loc['username']}\n\n"
        keyboard.append([
            InlineKeyboardButton(f"✅ Onayla", callback_data=f"approve_{idx}"),
            InlineKeyboardButton("❌ Reddet", callback_data=f"reject_{idx}")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def approve_location(query, idx):
    locations = load_data(DATA_FILE)
    if idx < len(locations):
        locations[idx]["approved"] = True
        save_data(DATA_FILE, locations)
        await query.edit_message_text(f"✅ Konum onaylandı: {locations[idx]['description']}")
    else:
        await query.edit_message_text("❌ Konum bulunamadı")

async def reject_location(query, idx):
    locations = load_data(DATA_FILE)
    if idx < len(locations):
        desc = locations[idx]['description']
        locations.pop(idx)
        save_data(DATA_FILE, locations)
        await query.edit_message_text(f"❌ Konum reddedildi: {desc}")
    else:
        await query.edit_message_text("❌ Konum bulunamadı")

async def main():
    app = Application.builder().token(TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^add_location$")],
        states={
            LOCATION: [MessageHandler(filters.LOCATION, handle_location)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_description)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_time)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
