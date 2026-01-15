"""
УДАЛЁННЫЙ Flask сервер для транскрибации видео (для Oracle VM)
Использует Gemini 2.5 Flash для качественной транскрибации
+ Perplexity API для проверки фактов
Отличие от local_app.py: слушает на 0.0.0.0 для удалённого доступа
"""

from flask import Flask, request, jsonify, send_file, send_from_directory
import os
import logging
import uuid
import time
import threading
from datetime import datetime
from pathlib import Path
from collections import deque

# Импорт модулей для обработки видео и транскрибации
try:
    from real_downloader import download_video, extract_audio
    from local_transcriber import transcribe_with_gemini_2_5
    HAS_MODULES = True
    print("✅ Модули успешно загружены")
except ImportError as e:
    print(f"⚠️ ОШИБКА: Не удалось импортировать модули: {e}")
    HAS_MODULES = False

# Импорт модуля проверки фактов
try:
    from fact_checker import verify_facts
    HAS_FACT_CHECKER = True
    print("✅ Модуль проверки фактов загружен")
except ImportError as e:
    print(f"⚠️ Модуль проверки фактов недоступен: {e}")
    HAS_FACT_CHECKER = False

# Хранилище логов для отображения на веб-странице
LOG_BUFFER = deque(maxlen=1000)  # Хранит последние 1000 логов

class WebLogHandler(logging.Handler):
    """Кастомный handler для сохранения логов в буфер"""
    def emit(self, record):
        log_entry = self.format(record)
        LOG_BUFFER.append(log_entry)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Добавляем веб-handler
web_handler = WebLogHandler()
web_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(web_handler)

# Также добавляем для root logger
logging.getLogger('').addHandler(web_handler)

# Создаем Flask приложение
app = Flask(__name__)

# Создаем папки для хранения файлов
AUDIO_FOLDER = Path("audio_files")
AUDIO_FOLDER.mkdir(exist_ok=True)

# Словарь для хранения путей к аудиофайлам
AUDIO_FILES = {}

# Словарь для хранения путей к видеофайлам
VIDEO_FILES = {}


def cleanup_old_audio_files():
    """Очистка старых аудиофайлов (старше 1 часа)"""
    current_time = time.time()
    files_to_remove = []

    for audio_id, path in list(AUDIO_FILES.items()):
        if not os.path.exists(path):
            files_to_remove.append(audio_id)
            continue

        file_modified_time = os.path.getmtime(path)
        if current_time - file_modified_time > 3600:  # 1 час
            try:
                os.remove(path)
                logger.info(f"🗑️ Удален старый аудиофайл: {path}")
                files_to_remove.append(audio_id)
            except Exception as e:
                logger.error(f"❌ Ошибка при удалении {path}: {e}")

    for audio_id in files_to_remove:
        AUDIO_FILES.pop(audio_id, None)

def cleanup_old_video_files():
    """Очистка старых видеофайлов (старше 1 часа)"""
    current_time = time.time()
    files_to_remove = []

    for video_id, path in list(VIDEO_FILES.items()):
        if not os.path.exists(path):
            files_to_remove.append(video_id)
            continue

        file_modified_time = os.path.getmtime(path)
        if current_time - file_modified_time > 3600:  # 1 час
            try:
                os.remove(path)
                logger.info(f"🗑️ Удален старый видеофайл: {path}")
                files_to_remove.append(video_id)
            except Exception as e:
                logger.error(f"❌ Ошибка при удалении {path}: {e}")

    for video_id in files_to_remove:
        VIDEO_FILES.pop(video_id, None)



def run_cleanup_task():
    """Периодически запускает очистку старых аудиофайлов"""
    while True:
        try:
            cleanup_old_audio_files()
            cleanup_old_video_files()
        except Exception as e:
            logger.error(f"❌ Ошибка при выполнении очистки: {e}")
        time.sleep(900)  # 15 минут


# Запускаем фоновую очистку
cleanup_thread = threading.Thread(target=run_cleanup_task, daemon=True)
cleanup_thread.start()


@app.route('/')
def index():
    """Главная страница с интерфейсом"""
    return send_file('index.html')


@app.route('/extract-audio-only', methods=['POST'])
def extract_audio_only():
    """Извлечение только аудио без транскрибации"""
    # Очищаем буфер логов перед началом
    LOG_BUFFER.clear()

    try:
        # Получаем данные из запроса
        data = request.get_json() or {}
        video_url = data.get('video_url', '').strip()

        logger.info(f"📥 Получен запрос на извлечение аудио: URL={video_url}")

        # Проверяем обязательные поля
        if not video_url:
            return jsonify({
                "status": "error",
                "message": "❌ URL видео обязателен",
                "logs": list(LOG_BUFFER)
            }), 400

        if not HAS_MODULES:
            return jsonify({
                "status": "error",
                "message": "❌ Необходимые модули не установлены",
                "logs": list(LOG_BUFFER)
            }), 500

        # Загружаем видео
        logger.info("📹 Загрузка видео...")
        video_path = download_video(video_url)
        logger.info(f"✅ Видео загружено: {video_path}")

        # Извлекаем аудио
        logger.info("🎵 Извлечение аудио...")
        audio_path = extract_audio(video_path)
        logger.info(f"✅ Аудио извлечено: {audio_path}")

        # Генерируем уникальный ID для аудио
        audio_id = str(uuid.uuid4())

        # Копируем аудиофайл в постоянную папку
        permanent_audio_path = AUDIO_FOLDER / f"{audio_id}.mp3"
        import shutil
        shutil.copy2(audio_path, permanent_audio_path)
        AUDIO_FILES[audio_id] = str(permanent_audio_path)
        logger.info(f"💾 Аудиофайл сохранен: ID={audio_id}")

        # Удаляем временные файлы
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
            if os.path.exists(audio_path) and audio_path != str(permanent_audio_path):
                os.remove(audio_path)
        except Exception as cleanup_error:
            logger.error(f"⚠️ Ошибка при очистке: {cleanup_error}")

        # Возвращаем результат с логами
        result = {
            "status": "success",
            "message": "✅ Аудио извлечено успешно",
            "audio_id": audio_id,
            "logs": list(LOG_BUFFER)
        }

        logger.info("📤 Отправка результата клиенту")
        return jsonify(result)

    except Exception as e:
        logger.error(f"❌ Ошибка в /extract-audio-only: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"❌ Ошибка: {str(e)}",
            "logs": list(LOG_BUFFER)
        }), 500


@app.route('/process', methods=['POST'])
def process_video():
    """Обработка видео: загрузка, извлечение аудио, транскрибация"""
    # Очищаем буфер логов перед началом
    LOG_BUFFER.clear()

    try:
        # Получаем данные из запроса
        data = request.get_json() or {}
        video_url = data.get('video_url', '').strip()
        api_key = data.get('api_key', '').strip()
        language = data.get('language', 'ru')
        model = data.get('model', 'gemini-2.5-flash')  # Поддержка выбора модели

        logger.info(f"📥 Получен запрос: URL={video_url}, Lang={language}")

        # Проверяем обязательные поля
        if not video_url:
            return jsonify({
                "status": "error",
                "message": "❌ URL видео обязателен",
                "logs": list(LOG_BUFFER)
            }), 400

        if not api_key:
            return jsonify({
                "status": "error",
                "message": "❌ API ключ Gemini обязателен",
                "logs": list(LOG_BUFFER)
            }), 400

        if not HAS_MODULES:
            return jsonify({
                "status": "error",
                "message": "❌ Необходимые модули не установлены. Проверьте requirements_local.txt",
                "logs": list(LOG_BUFFER)
            }), 500

        # Загружаем видео
        logger.info("📹 Загрузка видео...")
        video_path = download_video(video_url)
        logger.info(f"✅ Видео загружено: {video_path}")

        # Извлекаем аудио
        logger.info("🎵 Извлечение аудио...")
        audio_path = extract_audio(video_path)
        logger.info(f"✅ Аудио извлечено: {audio_path}")

        # Транскрибируем с помощью Gemini 2.5
        logger.info("🤖 Транскрибация с помощью Gemini 2.5...")
        try:
            transcript, summary = transcribe_with_gemini_2_5(audio_path, api_key, language, model)
            logger.info("✅ Транскрибация завершена успешно")
        except Exception as transcribe_error:
            logger.error(f"❌ Ошибка транскрибации: {transcribe_error}")
            transcript = f"Ошибка транскрибации: {str(transcribe_error)}"
            summary = "Не удалось создать саммари из-за ошибки"

        # Генерируем уникальный ID для аудио
        audio_id = str(uuid.uuid4())

        # Копируем аудиофайл в постоянную папку
        permanent_audio_path = AUDIO_FOLDER / f"{audio_id}.mp3"
        import shutil
        shutil.copy2(audio_path, permanent_audio_path)
        AUDIO_FILES[audio_id] = str(permanent_audio_path)
        logger.info(f"💾 Аудиофайл сохранен: ID={audio_id}")

        # Удаляем временные файлы
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
                logger.info(f"🗑️ Удален временный видеофайл")
            if os.path.exists(audio_path) and audio_path != str(permanent_audio_path):
                os.remove(audio_path)
                logger.info(f"🗑️ Удален временный аудиофайл")
        except Exception as cleanup_error:
            logger.error(f"⚠️ Ошибка при очистке: {cleanup_error}")

        # Возвращаем результат с логами
        result = {
            "status": "success",
            "message": "✅ Обработка завершена успешно",
            "transcript": transcript,
            "summary": summary,
            "audio_id": audio_id,
            "logs": list(LOG_BUFFER)
        }

        logger.info("📤 Отправка результата клиенту")
        return jsonify(result)

    except Exception as e:
        logger.error(f"❌ Ошибка в /process: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"❌ Ошибка обработки: {str(e)}",
            "logs": list(LOG_BUFFER)
        }), 500


@app.route('/verify-facts', methods=['POST'])
def verify_facts_endpoint():
    """
    Проверка фактов в транскрибированном тексте через Perplexity API

    Ожидает JSON:
    {
        "transcript": "текст для проверки",
        "api_key": "ключ Perplexity API",
        "language": "ru" или "en"
    }
    """
    LOG_BUFFER.clear()

    try:
        data = request.get_json() or {}
        transcript = data.get('transcript', '').strip()
        api_key = data.get('api_key', '').strip()
        language = data.get('language', 'ru')

        logger.info(f"🔍 Получен запрос на проверку фактов, длина текста: {len(transcript)} символов")

        # Валидация
        if not transcript:
            return jsonify({
                "status": "error",
                "message": "❌ Текст для проверки обязателен",
                "logs": list(LOG_BUFFER)
            }), 400

        if not api_key:
            return jsonify({
                "status": "error",
                "message": "❌ API ключ Perplexity обязателен",
                "logs": list(LOG_BUFFER)
            }), 400

        if not HAS_FACT_CHECKER:
            return jsonify({
                "status": "error",
                "message": "❌ Модуль проверки фактов недоступен",
                "logs": list(LOG_BUFFER)
            }), 500

        # Проверяем факты
        logger.info("🌐 Отправка запроса в Perplexity API...")
        result = verify_facts(transcript, api_key, language)

        if result.get("status") == "error":
            logger.error(f"❌ Ошибка проверки: {result.get('message')}")
            return jsonify({
                "status": "error",
                "message": result.get("message", "Неизвестная ошибка"),
                "logs": list(LOG_BUFFER)
            }), 500

        logger.info("✅ Проверка фактов завершена успешно")

        # Добавляем логи к результату
        result["logs"] = list(LOG_BUFFER)

        return jsonify(result)

    except Exception as e:
        logger.error(f"❌ Ошибка в /verify-facts: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"❌ Ошибка: {str(e)}",
            "logs": list(LOG_BUFFER)
        }), 500


@app.route('/download-audio/<audio_id>')
def download_audio(audio_id):
    """Скачивание аудиофайла по ID"""
    try:
        if audio_id not in AUDIO_FILES:
            logger.warning(f"⚠️ Запрос несуществующего аудио: {audio_id}")
            return jsonify({
                "status": "error",
                "message": "Аудиофайл не найден"
            }), 404

        audio_path = AUDIO_FILES[audio_id]

        if not os.path.exists(audio_path):
            logger.warning(f"⚠️ Файл не существует: {audio_path}")
            return jsonify({
                "status": "error",
                "message": "Файл не существует на сервере"
            }), 404

        filename = f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        logger.info(f"📥 Скачивание: {audio_path} -> {filename}")

        return send_file(
            audio_path,
            as_attachment=True,
            download_name=filename,
            mimetype='audio/mp3'
        )

    except Exception as e:
        logger.error(f"❌ Ошибка при скачивании: {e}")
        return jsonify({
            "status": "error",
            "message": f"Ошибка: {str(e)}"
        }), 500



@app.route('/download-video/<video_id>')
def download_video_file(video_id):
    """Скачивание видеофайла по ID"""
    try:
        if video_id not in VIDEO_FILES:
            logger.warning(f"⚠️ Запрос несуществующего видео: {video_id}")
            return jsonify({
                "status": "error",
                "message": "Видеофайл не найден"
            }), 404

        video_path = VIDEO_FILES[video_id]

        if not os.path.exists(video_path):
            logger.warning(f"⚠️ Файл не существует: {video_path}")
            return jsonify({
                "status": "error",
                "message": "Файл не существует на сервере"
            }), 404

        filename = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        logger.info(f"📥 Скачивание видео: {video_path} -> {filename}")

        return send_file(
            video_path,
            as_attachment=True,
            download_name=filename,
            mimetype='video/mp4'
        )

    except Exception as e:
        logger.error(f"❌ Ошибка при скачивании видео: {e}")
        return jsonify({
            "status": "error",
            "message": f"Ошибка: {str(e)}"
        }), 500


@app.route('/download-video-only', methods=['POST'])
def download_video_only():
    """Скачивание только видео (без транскрипации)"""
    try:
        data = request.get_json()
        video_url = data.get('video_url')

        if not video_url:
            return jsonify({
                "status": "error",
                "message": "URL видео обязателен"
            }), 400

        logger.info(f"📥 Запрос на скачивание видео: {video_url}")

        # Скачиваем видео
        video_path = download_video(video_url)

        if not video_path or not os.path.exists(video_path):
            return jsonify({
                "status": "error",
                "message": "Не удалось скачать видео"
            }), 500

        # Генерируем ID для видео
        video_id = str(uuid.uuid4())
        VIDEO_FILES[video_id] = video_path

        logger.info(f"✅ Видео загружено: ID={video_id}")

        return jsonify({
            "status": "completed",
            "message": "Видео загружено успешно",
            "video_id": video_id
        })

    except Exception as e:
        logger.error(f"❌ Ошибка при скачивании видео: {e}")
        return jsonify({
            "status": "error",
            "message": f"Ошибка: {str(e)}"
        }), 500



@app.route('/extract-audio-from-video/<video_id>', methods=['POST'])
def extract_audio_from_video(video_id):
    """Извлечение аудио из уже скачанного видео"""
    try:
        if video_id not in VIDEO_FILES:
            logger.warning(f"⚠️ Запрос несуществующего видео: {video_id}")
            return jsonify({
                "status": "error",
                "message": "Видеофайл не найден"
            }), 404

        video_path = VIDEO_FILES[video_id]

        if not os.path.exists(video_path):
            logger.warning(f"⚠️ Видеофайл не существует: {video_path}")
            return jsonify({
                "status": "error",
                "message": "Видеофайл не существует на сервере"
            }), 404

        logger.info(f"🎵 Извлечение аудио из видео: {video_path}")

        # Извлекаем аудио
        from real_downloader import extract_audio
        audio_path = extract_audio(video_path)

        if not audio_path or not os.path.exists(audio_path):
            return jsonify({
                "status": "error",
                "message": "Не удалось извлечь аудио"
            }), 500

        # Генерируем ID для аудио и сохраняем
        audio_id = str(uuid.uuid4())
        permanent_audio_path = AUDIO_FOLDER / f"{audio_id}.mp3"

        import shutil
        shutil.copy2(audio_path, permanent_audio_path)
        AUDIO_FILES[audio_id] = str(permanent_audio_path)

        logger.info(f"✅ Аудио извлечено: ID={audio_id}")

        return jsonify({
            "status": "completed",
            "message": "Аудио извлечено успешно",
            "audio_id": audio_id
        })

    except Exception as e:
        logger.error(f"❌ Ошибка при извлечении аудио: {e}")
        return jsonify({
            "status": "error",
            "message": f"Ошибка: {str(e)}"
        }), 500


@app.route('/transcribe-from-audio/<audio_id>', methods=['POST'])
def transcribe_from_audio(audio_id):
    """Транскрибация из уже извлеченного аудио"""
    try:
        if audio_id not in AUDIO_FILES:
            logger.warning(f"⚠️ Запрос несуществующего аудио: {audio_id}")
            return jsonify({
                "status": "error",
                "message": "Аудиофайл не найден"
            }), 404

        audio_path = AUDIO_FILES[audio_id]

        if not os.path.exists(audio_path):
            logger.warning(f"⚠️ Аудиофайл не существует: {audio_path}")
            return jsonify({
                "status": "error",
                "message": "Аудиофайл не существует на сервере"
            }), 404

        # Получаем параметры
        data = request.get_json() or {}
        api_key = data.get('api_key', '')
        model = data.get('model', 'gemini-2.5-flash')
        language = data.get('language', 'ru')

        if not api_key:
            return jsonify({
                "status": "error",
                "message": "API ключ Gemini обязателен"
            }), 400

        logger.info(f"📝 Транскрибация аудио: {audio_path}")

        # Транскрибируем
        from local_transcriber import transcribe_with_gemini_2_5
        result = transcribe_with_gemini_2_5(
            audio_path=audio_path,
            api_key=api_key,
            model=model,
            language=language
        )

        if not result or result.get('status') == 'error':
            return jsonify({
                "status": "error",
                "message": result.get('message', 'Ошибка транскрибации')
            }), 500

        logger.info(f"✅ Транскрибация завершена")

        return jsonify({
            "status": "completed",
            "transcription": result.get('transcription', ''),
            "summary": result.get('summary', ''),
            "audio_id": audio_id,
            "message": "Транскрибация завершена успешно"
        })

    except Exception as e:
        logger.error(f"❌ Ошибка при транскрибации: {e}")
        return jsonify({
            "status": "error",
            "message": f"Ошибка: {str(e)}"
        }), 500


@app.route('/generate-infographic', methods=['POST'])
def generate_infographic():
    """
    Генерация инфографики по описанию пользователя.
    Двухэтапный процесс:
    1. gemini-2.0-flash анализирует описание и создаёт детальный промпт
    2. gemini-2.5-flash-image генерирует картинку

    Ожидает JSON:
    {
        "description": "описание инфографики",
        "api_key": "ключ Gemini API"
    }
    """
    import requests
    import base64

    LOG_BUFFER.clear()

    try:
        data = request.get_json() or {}
        description = data.get('description', '').strip()
        api_key = data.get('api_key', '').strip()

        logger.info(f"🎨 Запрос на генерацию инфографики, описание: {len(description)} символов")

        # Валидация
        if not description:
            return jsonify({
                "status": "error",
                "message": "❌ Описание инфографики обязательно",
                "logs": list(LOG_BUFFER)
            }), 400

        if not api_key:
            return jsonify({
                "status": "error",
                "message": "❌ API ключ Gemini обязателен",
                "logs": list(LOG_BUFFER)
            }), 400

        # ШАГ 1: Анализ описания и создание промпта
        logger.info("📝 Шаг 1: Анализ описания (gemini-2.0-flash)...")

        url_text = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}'

        prompt_request = {
            'contents': [{
                'parts': [{
                    'text': f'''You are an expert at creating prompts for image generation.
Based on this description, create a detailed English prompt for generating a professional infographic:

DESCRIPTION:
{description}

Create a detailed prompt that describes:
1. Visual style (colors, layout, typography)
2. Specific elements to include
3. Composition and arrangement
4. Professional quality indicators

Output ONLY the image generation prompt, nothing else. Make it detailed but under 200 words.'''
                }]
            }]
        }

        response = requests.post(url_text, json=prompt_request, timeout=60)

        if response.status_code != 200:
            error_msg = response.json().get('error', {}).get('message', 'Unknown error')
            logger.error(f"❌ Ошибка анализа: {error_msg}")
            return jsonify({
                "status": "error",
                "message": f"❌ Ошибка анализа описания: {error_msg}",
                "logs": list(LOG_BUFFER)
            }), 500

        result = response.json()
        image_prompt = ''
        for candidate in result.get('candidates', []):
            for part in candidate.get('content', {}).get('parts', []):
                if 'text' in part:
                    image_prompt = part['text'].strip()
                    break

        if not image_prompt:
            return jsonify({
                "status": "error",
                "message": "❌ Не удалось создать промпт для изображения",
                "logs": list(LOG_BUFFER)
            }), 500

        logger.info(f"✅ Промпт создан ({len(image_prompt)} символов)")

        # ШАГ 2: Генерация изображения
        logger.info("🍌 Шаг 2: Генерация картинки (gemini-2.5-flash-image)...")

        url_image = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key={api_key}'

        image_request = {
            'contents': [{
                'parts': [{
                    'text': image_prompt
                }]
            }],
            'generationConfig': {
                'responseModalities': ['image', 'text']
            }
        }

        # Пробуем несколько раз (модель может быть перегружена)
        max_attempts = 3
        for attempt in range(max_attempts):
            logger.info(f"   Попытка {attempt+1}/{max_attempts}...")
            response = requests.post(url_image, json=image_request, timeout=120)

            if response.status_code == 200:
                result = response.json()
                for candidate in result.get('candidates', []):
                    for part in candidate.get('content', {}).get('parts', []):
                        if 'inlineData' in part:
                            image_data = part['inlineData']['data']
                            mime_type = part['inlineData'].get('mimeType', 'image/png')

                            logger.info(f"✅ Картинка сгенерирована!")

                            return jsonify({
                                "status": "success",
                                "message": "✅ Инфографика создана успешно",
                                "image_data": image_data,
                                "mime_type": mime_type,
                                "prompt_used": image_prompt,
                                "logs": list(LOG_BUFFER)
                            })
                        elif 'text' in part:
                            logger.info(f"📝 Текстовый ответ: {part['text'][:100]}...")
                break
            elif response.status_code == 503:
                logger.warning("⏳ Модель перегружена, ждём 10 секунд...")
                import time
                time.sleep(10)
            elif response.status_code == 429:
                logger.error("❌ Квота исчерпана")
                return jsonify({
                    "status": "error",
                    "message": "❌ Квота API исчерпана. Попробуйте позже.",
                    "logs": list(LOG_BUFFER)
                }), 429
            else:
                error_msg = response.json().get('error', {}).get('message', 'Unknown error')
                logger.error(f"❌ Ошибка генерации: {error_msg}")
                return jsonify({
                    "status": "error",
                    "message": f"❌ Ошибка генерации: {error_msg}",
                    "logs": list(LOG_BUFFER)
                }), 500

        return jsonify({
            "status": "error",
            "message": "❌ Не удалось сгенерировать картинку после нескольких попыток",
            "logs": list(LOG_BUFFER)
        }), 500

    except Exception as e:
        logger.error(f"❌ Ошибка в /generate-infographic: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"❌ Ошибка: {str(e)}",
            "logs": list(LOG_BUFFER)
        }), 500


@app.route('/status')
def status():
    """Статус сервера и доступных модулей"""
    return jsonify({
        "status": "running",
        "modules_loaded": HAS_MODULES,
        "fact_checker_available": HAS_FACT_CHECKER,
        "audio_files_count": len(AUDIO_FILES),
        "video_files_count": len(VIDEO_FILES),
        "gemini_model": "gemini-2.5-flash (Gemini 2.5 Flash - 1000 запросов/день)",
        "message": "✅ Сервер работает нормально" if HAS_MODULES else "⚠️ Некоторые модули не загружены",
        "mode": "remote",
        "features": {
            "transcription": HAS_MODULES,
            "fact_checking": HAS_FACT_CHECKER,
            "video_download": HAS_MODULES,
            "audio_extraction": HAS_MODULES,
            "infographic_generation": True
        }
    })


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🎬 УДАЛЁННЫЙ ТРАНСКРИБЕР ВИДЕО (ORACLE VM)")
    print("="*60)
    print(f"🤖 Модель: Gemini 2.5 Flash (gemini-2.5-flash)")
    print(f"🔍 Проверка фактов: {'Да (Perplexity API)' if HAS_FACT_CHECKER else 'Нет ⚠️'}")
    print(f"⚡ Лимит: 1000 запросов в день (FREE)")
    print(f"📂 Папка для аудио: {AUDIO_FOLDER.absolute()}")
    print(f"✅ Модули загружены: {'Да' if HAS_MODULES else 'Нет ⚠️'}")
    print("="*60)
    print(f"🌐 Сервер запущен на: 0.0.0.0:5000")
    print(f"💡 Доступ по IP сервера из любой сети")
    print("="*60 + "\n")

    # Запускаем сервер для удалённого доступа
    app.run(
        host='0.0.0.0',  # Слушаем на всех интерфейсах
        port=5000,
        debug=False,  # В production режиме отключаем debug
        use_reloader=False  # Отключаем перезагрузку
    )
