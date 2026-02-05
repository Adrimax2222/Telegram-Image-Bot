# 📸 Bot de Telegram - Organizador de Fotos por Hashtags

Bot de Telegram que organiza fotos por hashtags y permite buscarlas por categorías.

## 🚀 Características

- 📂 Organiza fotos automáticamente por hashtags
- 🔍 Búsqueda por categorías en chat privado
- 🤐 No ensucia el chat del grupo
- ☁️ Desplegable en Render (plan gratuito)

## 📦 Instalación en Render

1. Haz fork de este repositorio
2. Crea un nuevo **Web Service** en Render
3. Conecta tu repositorio de GitHub
4. Configura las variables de entorno:
   - `TELEGRAM_TOKEN`: Tu token del bot de Telegram
5. Render detectará automáticamente el `requirements.txt`
6. Comando de inicio: `python bot.py`

## 🎯 Uso

1. **En grupos**: Añade el bot y envía fotos con hashtags (ej: `#vacaciones #playa`)
2. **En privado**: Usa `/categorias` para ver todas las categorías y buscar fotos

## 🛠️ Tecnologías

- Python 3.11+
- pyTelegramBotAPI
- SQLite
- Flask
