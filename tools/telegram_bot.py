"""
Bot de Telegram para controlar Cortana desde el celular.

Setup:
1. Habla con @BotFather en Telegram
2. Crea un bot con /newbot
3. Copia el token y ponlo en .env como TELEGRAM_TOKEN
4. Escribe a tu bot, luego corre: python -c "from tools.telegram_bot import get_my_chat_id; get_my_chat_id()"
5. Copia el chat_id resultante a .env como TELEGRAM_CHAT_ID
"""

import os
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.WARNING)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def _is_authorized(update: Update) -> bool:
    """Solo el dueno puede usar el bot."""
    if not TELEGRAM_CHAT_ID:
        return True  # Sin restriccion si no se configuro
    return str(update.effective_chat.id) == str(TELEGRAM_CHAT_ID)


async def _start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        await update.message.reply_text("Acceso denegado.")
        return
    await update.message.reply_text(
        "Cortana activa.\n\n"
        "Puedes escribirme directamente. Comandos disponibles:\n"
        "/start — Este mensaje\n"
        "/estado — Estado del sistema\n"
        "/notas — Lista tus notas guardadas\n"
        "/hora — Fecha y hora actual"
    )


async def _estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    from tools.datetime_tool import get_current_datetime
    dt = get_current_datetime()
    await update.message.reply_text(f"Sistema operativo.\n\n{dt}")


async def _notas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    from tools.notes import list_notes
    await update.message.reply_text(list_notes())


async def _hora(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    from tools.datetime_tool import get_current_datetime
    await update.message.reply_text(get_current_datetime())


async def _handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        await update.message.reply_text("Acceso denegado.")
        return

    user_text = update.message.text
    await update.message.reply_chat_action("typing")

    from core.llm import chat
    response = chat(user_text)
    await update.message.reply_text(response)


async def _handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa mensajes de voz enviados desde el celular."""
    if not _is_authorized(update):
        return

    await update.message.reply_text("Procesando mensaje de voz...")
    file = await context.bot.get_file(update.message.voice.file_id)

    import tempfile, subprocess
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        ogg_path = f.name
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name

    try:
        await file.download_to_drive(ogg_path)
        # Convertir ogg a wav usando ffmpeg si esta disponible
        result = subprocess.run(
            ["ffmpeg", "-i", ogg_path, wav_path, "-y"],
            capture_output=True
        )
        if result.returncode == 0:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language="es-ES")
            from core.llm import chat
            response = chat(text)
            await update.message.reply_text(f"Entendi: {text}\n\nCortana: {response}")
        else:
            await update.message.reply_text("No pude procesar el audio. Instala ffmpeg para habilitar mensajes de voz.")
    except Exception as e:
        await update.message.reply_text(f"Error procesando voz: {e}")
    finally:
        import os
        for p in [ogg_path, wav_path]:
            try:
                os.unlink(p)
            except Exception:
                pass


def send_message_sync(text: str):
    """Envia un mensaje desde Cortana al usuario en Telegram (llamada sincrona)."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return

    async def _send():
        from telegram import Bot
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)

    try:
        asyncio.run(_send())
    except Exception as e:
        print(f"[Telegram] Error enviando mensaje: {e}")


def run_bot():
    """Inicia el bot de Telegram (bloqueante)."""
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_TOKEN no configurado en .env")
        return

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", _start))
    app.add_handler(CommandHandler("estado", _estado))
    app.add_handler(CommandHandler("notas", _notas))
    app.add_handler(CommandHandler("hora", _hora))
    app.add_handler(MessageHandler(filters.VOICE, _handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message))

    print("Bot de Telegram activo. Escribe a tu bot desde el celular.")
    app.run_polling()


def get_my_chat_id():
    """Utility para obtener tu chat_id. Ejecutar una vez despues de escribirle al bot."""
    if not TELEGRAM_TOKEN:
        print("Primero configura TELEGRAM_TOKEN en .env")
        return

    async def _get():
        from telegram import Bot
        bot = Bot(token=TELEGRAM_TOKEN)
        updates = await bot.get_updates()
        if updates:
            for u in updates:
                if u.message:
                    print(f"Tu chat_id es: {u.message.chat.id}")
                    print(f"Agrega esto a tu .env: TELEGRAM_CHAT_ID={u.message.chat.id}")
                    return
        print("No se encontraron mensajes. Escribe algo a tu bot primero.")

    asyncio.run(_get())
