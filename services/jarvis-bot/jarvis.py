#!/usr/bin/env python3
"""
Jarvis Telegram Bot - с поддержкой видео генерации
Gemini AI + Image Generation + Video Generation (Veo 3.1)
"""

import logging
import requests
import base64
from io import BytesIO
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai
from google.genai import types

# Конфигурация
BOT_TOKEN = "8306320317:AAETBZUKx4XJJH7_FUvv8xIz3FtTIPEnB3A"
GEMINI_API_KEY = "AIzaSyAXlZOVd0_igKYnNaQqJtBfQ4Ch-QGu9cc"
IMAGE_SERVICE_URL = "http://localhost:5680/generate"
VIDEO_SERVICE_URL = "http://localhost:5681/generate"

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Gemini клиент
client = genai.Client(api_key=GEMINI_API_KEY)

# История разговоров (простой формат: список сообщений)
conversations = {}

# Состояние ожидания фото для видео
waiting_for_video_photo = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    keyboard = [
        ["🎨 Картинка", "🎬 Видео"],
        ["🧹 Очистить", "❓ Помощь"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "Я Jarvis - AI ассистент с суперспособностями:\n\n"
        "💬 **Чат** - просто напиши мне\n"
        "🎨 **Картинки** - /image [описание] или \"нарисуй...\"\n"
        "🎬 **Видео** - /video [описание] или отправь фото\n"
        "📷 **Анализ фото** - отправь любое фото\n\n"
        "Для видео из фото:\n"
        "1. Нажми 🎬 Видео или /video\n"
        "2. Отправь фото\n"
        "3. Жди генерацию (~2-3 мин)",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    await update.message.reply_text(
        "🤖 **Команды Jarvis:**\n\n"
        "/start - Начать\n"
        "/help - Эта справка\n"
        "/clear - Очистить историю\n"
        "/image [описание] - Создать картинку\n"
        "/video [описание] - Создать видео из текста\n"
        "/video + фото - Анимировать фото\n\n"
        "**Триггеры в тексте:**\n"
        "• \"нарисуй...\" → картинка\n"
        "• \"сгенерируй видео...\" → видео\n\n"
        "**Фото:**\n"
        "• Просто фото → анализ\n"
        "• Фото после /video → видео из фото",
        parse_mode='Markdown'
    )


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистка истории"""
    user_id = update.effective_user.id
    conversations[user_id] = []
    waiting_for_video_photo.pop(user_id, None)
    await update.message.reply_text("🧹 История очищена!")


async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Генерация изображения"""
    prompt = ' '.join(context.args) if context.args else None
    
    if not prompt:
        await update.message.reply_text("✏️ Укажи описание: /image красивый закат")
        return
    
    msg = await update.message.reply_text("🎨 Рисую...")
    
    try:
        response = requests.post(
            IMAGE_SERVICE_URL,
            json={"prompt": prompt},
            timeout=120
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('image_base64'):
                image_bytes = base64.b64decode(data['image_base64'])
                await update.message.reply_photo(
                    photo=BytesIO(image_bytes),
                    caption=f"🎨 {prompt[:200]}"
                )
                await msg.delete()
            else:
                await msg.edit_text("❌ Не удалось создать изображение")
        else:
            await msg.edit_text(f"❌ Ошибка сервиса: {response.status_code}")
            
    except Exception as e:
        logger.error(f"Image error: {e}")
        await msg.edit_text(f"❌ Ошибка: {str(e)[:100]}")


async def generate_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /video - генерация видео"""
    user_id = update.effective_user.id
    prompt = ' '.join(context.args) if context.args else None
    
    if prompt:
        # Генерация видео из текста - отправляем ссылку
        await handle_video_request(update, context, prompt)
    else:
        # Ожидаем фото для видео
        waiting_for_video_photo[user_id] = True
        await update.message.reply_text(
            "🎬 Отправь фото, которое хочешь анимировать.\n"
            "Или добавь описание: /video кот прыгает"
        )


async def handle_video_request(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str = None):
    """Отправляет ссылку на Veo Studio для генерации видео"""
    chat_id = update.effective_chat.id
    
    veo_url = "https://vision-preliminary-adelaide-portsmouth.trycloudflare.com/veo/"
    
    message = f"""🎬 *Veo Video Studio*

Генерация видео доступна через веб-интерфейс:
🔗 {veo_url}

*Возможности:*
• Генерация видео по текстовому описанию
• Анимация изображений
• Выбор формата 16:9 или 9:16

*Стоимость:*
• Veo 3.0 Fast: ~$0.35/сек (~$2 за видео)
• Veo 3.1 Full: ~$0.70/сек (~$4 за видео)

💡 Нужен Google AI API ключ с включённым биллингом"""

    if prompt:
        message += f"\n\n*Ваш запрос:* {prompt}"
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=message,
        parse_mode='Markdown'
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фото"""
    user_id = update.effective_user.id
    photo = update.message.photo[-1]  # Лучшее качество
    caption = update.message.caption or ""
    
    # Скачиваем фото
    file = await context.bot.get_file(photo.file_id)
    photo_bytes = await file.download_as_bytearray()
    
    # Проверяем, ожидаем ли фото для видео
    if waiting_for_video_photo.get(user_id):
        waiting_for_video_photo.pop(user_id, None)
        # Отправляем ссылку на веб-интерфейс вместо генерации
        await handle_video_request(update, context, caption or "анимация фото")
        return
    
    # Проверяем триггеры для видео в caption
    video_triggers = ['видео', 'анимируй', 'анимация', 'animate', 'video']
    if any(trigger in caption.lower() for trigger in video_triggers):
        await handle_video_request(update, context, caption)
        return
    
    # Иначе - анализ фото через Gemini
    msg = await update.message.reply_text("🔍 Анализирую...")
    
    try:
        image_data = types.Part.from_bytes(
            data=bytes(photo_bytes),
            mime_type="image/jpeg"
        )
        
        prompt = caption if caption else "Опиши это изображение подробно на русском языке."
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, image_data]
        )
        
        await msg.edit_text(response.text[:4000])
        
    except Exception as e:
        logger.error(f"Photo analysis error: {e}")
        await msg.edit_text(f"❌ Ошибка анализа: {str(e)[:100]}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Кнопки клавиатуры
    if text == "🎨 Картинка":
        await update.message.reply_text("✏️ Напиши: /image [описание]")
        return
    if text == "🎬 Видео":
        waiting_for_video_photo[user_id] = True
        await update.message.reply_text(
            "🎬 Отправь фото для анимации\n"
            "Или: /video [описание] для видео из текста"
        )
        return
    if text == "🧹 Очистить":
        await clear(update, context)
        return
    if text == "❓ Помощь":
        await help_command(update, context)
        return
    
    # Триггеры для картинки
    image_triggers = ['нарисуй', 'нарисуйте', 'сгенерируй картинку', 'создай картинку', 'draw', 'generate image']
    for trigger in image_triggers:
        if text.lower().startswith(trigger):
            prompt = text[len(trigger):].strip()
            if prompt:
                context.args = prompt.split()
                await generate_image(update, context)
                return
    
    # Триггеры для видео
    video_triggers = ['сгенерируй видео', 'создай видео', 'generate video', 'make video']
    for trigger in video_triggers:
        if text.lower().startswith(trigger):
            prompt = text[len(trigger):].strip()
            if prompt:
                await handle_video_request(update, context, prompt)
                return
    
    # Обычный чат с Gemini (без истории - просто один запрос)
    msg = await update.message.reply_text("💭 Думаю...")
    
    try:
        # Простой запрос без истории (избегаем ошибку формата)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=text
        )
        
        reply = response.text
        await msg.edit_text(reply[:4000])
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        await msg.edit_text(f"❌ Ошибка: {str(e)[:100]}")


def main():
    """Запуск бота"""
    logger.info("Starting Jarvis Bot with Video support...")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("image", generate_image))
    app.add_handler(CommandHandler("video", generate_video))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Bot is running with polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()

