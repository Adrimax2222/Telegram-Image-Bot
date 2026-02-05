import os
import telebot
from telebot import types
import sqlite3
from threading import Thread
from flask import Flask
import re

# Configuración
TOKEN = os.getenv('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TOKEN)

# Flask para mantener activo el Web Service en Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot está activo", 200

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    app.run(host='0.0.0.0', port=10000)

# Inicializar base de datos
def init_db():
    conn = sqlite3.connect('photos.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT NOT NULL,
            hashtag TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Función para extraer hashtags
def extract_hashtags(text):
    if not text:
        return []
    hashtags = re.findall(r'#(\w+)', text)
    return [tag.lower() for tag in hashtags]

# Guardar foto en la base de datos
def save_photo(file_id, hashtags):
    conn = sqlite3.connect('photos.db', check_same_thread=False)
    cursor = conn.cursor()
    for tag in hashtags:
        cursor.execute('INSERT INTO photos (file_id, hashtag) VALUES (?, ?)', (file_id, tag))
    conn.commit()
    conn.close()

# Obtener todas las categorías (hashtags únicos)
def get_categories():
    conn = sqlite3.connect('photos.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT hashtag FROM photos ORDER BY hashtag')
    categories = [row[0] for row in cursor.fetchall()]
    conn.close()
    return categories

# Obtener fotos por categoría
def get_photos_by_category(hashtag):
    conn = sqlite3.connect('photos.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT file_id FROM photos WHERE hashtag = ?', (hashtag.lower(),))
    photos = [row[0] for row in cursor.fetchall()]
    conn.close()
    return photos

# Handler para fotos en grupos
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    # Solo procesar si tiene caption con hashtags
    if message.caption:
        hashtags = extract_hashtags(message.caption)
        if hashtags:
            file_id = message.photo[-1].file_id  # La foto de mejor calidad
            save_photo(file_id, hashtags)
            # NO responder nada para no ensuciar el chat

# Comando /categorias en chat privado
@bot.message_handler(commands=['categorias'])
def show_categories(message):
    # Solo funciona en chat privado
    if message.chat.type != 'private':
        return
    
    categories = get_categories()
    
    if not categories:
        bot.send_message(message.chat.id, "No hay categorías disponibles aún. Envía fotos con hashtags a tu grupo.")
        return
    
    # Crear teclado inline con las categorías
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(f"#{cat}", callback_data=f"cat_{cat}") for cat in categories]
    markup.add(*buttons)
    
    bot.send_message(message.chat.id, "📂 Selecciona una categoría:", reply_markup=markup)

# Handler para los botones de categorías
@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_'))
def handle_category_callback(call):
    hashtag = call.data.replace('cat_', '')
    photos = get_photos_by_category(hashtag)
    
    if not photos:
        bot.answer_callback_query(call.id, "No hay fotos en esta categoría")
        return
    
    bot.answer_callback_query(call.id, f"Enviando {len(photos)} foto(s)...")
    bot.send_message(call.message.chat.id, f"📸 Fotos de #{hashtag}:")
    
    # Enviar todas las fotos
    for file_id in photos:
        try:
            bot.send_photo(call.message.chat.id, file_id)
        except Exception as e:
            print(f"Error enviando foto: {e}")

# Comando /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    if message.chat.type == 'private':
        bot.reply_to(message, 
            "👋 ¡Hola! Soy tu bot organizador de fotos.\n\n"
            "📌 Añádeme a un grupo y envía fotos con hashtags.\n"
            "🔍 Usa /categorias para ver y buscar tus fotos por categoría."
        )

# Iniciar Flask en un hilo separado
if __name__ == '__main__':
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    print("✅ Bot iniciado correctamente")
    print("✅ Servidor Flask corriendo en puerto 10000")
    
    # Iniciar el bot
    bot.infinity_polling()
