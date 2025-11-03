#!/usr/bin/env python3
"""
Bot de Telegram que puede generar y buscar imágenes en chats permitidos.
Hecho para funcionar en Railway.
"""

import os
import asyncio
import logging
import sqlite3
from datetime import datetime
from typing import Optional, List
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image
import io

# ============ CONFIG ============ #
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # Token del bot
IMAGE_API_KEY = os.getenv("IMAGE_API_KEY")    # Token de proveedor de imágenes (opcional)
ALLOWED_CHAT_IDS = os.getenv("ALLOWED_CHAT_IDS", "")  # IDs de chats permitidos, separados por comas
MEDIA_DIR = os.getenv("MEDIA_DIR", "media")
DB_PATH = os.getenv("DB_PATH", "images.db")
# ================================= #

os.makedirs(MEDIA_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- Base de datos ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_file_id TEXT,
        local_path TEXT,
        prompt TEXT,
        tags TEXT,
        chat_id INTEGER,
        message_id INTEGER,
        created_at TEXT
    )
    """)
    conn.commit()
    conn.close()

def db_insert_image(file_id: Optional[str], path: str, prompt: str, tags: str, chat_id: int, msg_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO images (telegram_file_id, local_path, prompt, tags, chat_id, message_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (file_id, path, prompt, tags, chat_id, msg_id, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def db_search_images(query: str, allowed_chats: Optional[List[int]] = None, limit: int = 10):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    sql = "SELECT id, telegram_file_id, local_path, prompt, tags, chat_id, message_id, created_at FROM images WHERE (prompt LIKE ? OR tags LIKE ?)"
    params = [f"%{query}%", f"%{query}%"]
    if allowed_chats:
        placeholders = ",".join("?" for _ in allowed_chats)
        sql += f" AND chat_id IN ({placeholders})"
        params.extend(allowed_chats)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows

# ---------- Helpers ----------
def is_chat_allowed(chat_id: int) -> bool:
    if not ALLOWED_CHAT_IDS:
        return True
    allowed = [int(x.strip()) for x in ALLOWED_CHAT_IDS.split(",") if x.strip()]
    return chat_id in allowed

# ---------- Generador de imágenes ----------
async def generate_image_for_prompt(prompt: str):
    """
    Simula la generación de una imagen (usa una gris por defecto).
    Sustituye este código con la API real si quieres.
    """
    img = Image.new("RGB", (512, 512), color=(180, 180, 180))
    draw = Image.Draw.Draw(img)
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    filename = f"generated_{int(datetime.utcnow().timestamp())}.png"
    return bio.read(), filename

# ---------- Handlers ----------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 ¡Hola! Soy tu bot generador y buscador de imágenes.\n\n"
        "Comandos:\n"
        "/gen <texto> → genera una imagen\n"
        "/search <texto> → busca imágenes guardadas\n"
        "/help → muestra este mensaje"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_cmd(update, context)

async def gen_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_chat_allowed(chat_id):
        await update.message.reply_text("❌ Este chat no está autorizado.")
        return

    prompt = " ".join(context.args).strip()
    if not prompt:
        await update.message.reply_text("Usa: /gen <texto>")
        return

    msg = await update.message.reply_text("🎨 Generando imagen...")
    try:
        img_bytes, filename = await generate_image_for_prompt(prompt)
    except Exception as e:
        await msg.edit_text(f"Error generando imagen: {e}")
        return

    local_path = os.path.join(MEDIA_DIR, filename)
    with open(local_path, "wb") as f:
        f.write(img_bytes)

    with open(local_path, "rb") as f:
        sent = await context.bot.send_photo(chat_id, photo=InputFile(f), caption=f"🖼 Prompt: {prompt}")

    photo = sent.photo[-1]
    db_insert_image(photo.file_id, local_path, prompt, "", chat_id, sent.message_id)
    await msg.edit_text("✅ Imagen generada y guardada.")

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_chat_allowed(chat_id):
        await update.message.reply_text("❌ Este chat no está autorizado.")
        return

    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("Usa: /search <texto>")
        return

    rows = db_search_images(query, allowed_chats=[chat_id])
    if not rows:
        await update.message.reply_text("🔍 No se encontraron coincidencias.")
        return

    for row in rows:
        _, file_id, path, prompt, tags, c_id, msg_id, created = row
        caption = f"🖼 {prompt}\nGuardada: {created}"
        try:
            if file_id:
                await context.bot.send_photo(chat_id, photo=file_id, caption=caption)
            else:
                with open(path, "rb") as f:
                    await context.bot.send_photo(chat_id, photo=InputFile(f), caption=caption)
        except Exception:
            pass

async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_chat_allowed(chat_id):
        return

    photos = update.message.photo
    if not photos:
        return

    photo = photos[-1]
    file_id = photo.file_id
    message_id = update.message.message_id
    caption = update.message.caption or ""

    try:
        file = await context.bot.get_file(file_id)
        filename = f"p_{chat_id}_{message_id}.jpg"
        local_path = os.path.join(MEDIA_DIR, filename)
        await file.download_to_drive(local_path)
        db_insert_image(file_id, local_path, caption, "", chat_id, message_id)
    except Exception as e:
        logger.error(f"Error guardando foto: {e}")

# ---------- Main ----------
def main():
    token = TELEGRAM_TOKEN
    if not token:
        raise RuntimeError("⚠️ Falta TELEGRAM_TOKEN en variables de entorno.")
    init_db()
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("gen", gen_cmd))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, on_photo))

    logger.info("🤖 Bot iniciado correctamente.")
    app.run_polling()

if __name__ == "__main__":
    main()
