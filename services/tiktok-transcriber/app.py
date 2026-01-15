#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TikTok Transcriber with Google Sheets Integration
Веб-приложение для транскрибации видео с сохранением в Google Таблицы
"""

import os
import sys
import json
import uuid
import subprocess
import logging
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template_string
from flask_cors import CORS

# Настройка путей
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Import admin routes
try:
    from admin_routes import add_admin_routes
    HAS_ADMIN = True
except ImportError:
    HAS_ADMIN = False
STATIC_DIR = os.path.join(BASE_DIR, 'static', 'html')
DOWNLOADS_DIR = os.path.join(BASE_DIR, 'downloads')
TEMP_DIR = os.path.join(BASE_DIR, 'temp')

# Создаем необходимые директории
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask приложение
app = Flask(__name__)

# Add admin routes if available
if "HAS_ADMIN" in globals() and HAS_ADMIN:
    add_admin_routes(app)
CORS(app, origins=['*'], methods=['GET', 'POST', 'OPTIONS'])

# Словарь для хранения путей к аудио файлам
AUDIO_FILES = {}

# Импорт модулей транскрибации и Google Sheets
HAS_TRANSCRIBER = False
HAS_GOOGLE_SHEETS = False
google_sheets_manager = None

try:
    from transcriber import transcribe_with_gemini, transcribe_simple
    HAS_TRANSCRIBER = True
    logger.info("✅ Transcriber module loaded")
except ImportError as e:
    logger.warning(f"⚠️ Transcriber module not available: {e}")
    
    # Создадим простую функцию-заглушку
    def transcribe_simple(audio_path, api_key, model='gemini-2.5-flash', language='ru'):
        return "Транскрибация временно недоступна", "Требуется модуль transcriber.py"

try:
    from google_sheets import GoogleSheetsManager, init_google_sheets
    HAS_GOOGLE_SHEETS = True
    logger.info("✅ Google Sheets module loaded")
    
    # Инициализируем менеджер Google Sheets
    google_sheets_manager = init_google_sheets()
    if google_sheets_manager and google_sheets_manager.client:
        logger.info("✅ Google Sheets client initialized")
    else:
        logger.warning("⚠️ Google Sheets client not initialized (no credentials)")
except ImportError as e:
    logger.warning(f"⚠️ Google Sheets module not available: {e}")

@app.route('/')
@app.route('/fixed')
def index():
    """Главная страница"""
    # Проверяем существование index.html
    index_path = os.path.join(STATIC_DIR, 'index.html')
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        # Вернем базовую HTML страницу
        return render_template_string('''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>TikTok Transcriber</title>
</head>
<body>
    <h1>TikTok Transcriber</h1>
    <p>API готов к работе</p>
    <p>Google Sheets: {{ 'Подключено' if has_sheets else 'Не подключено' }}</p>
    <p>Transcriber: {{ 'Подключен' if has_transcriber else 'Не подключен' }}</p>
</body>
</html>
        ''', has_sheets=HAS_GOOGLE_SHEETS, has_transcriber=HAS_TRANSCRIBER)

@app.route('/health')
def health():
    """Проверка состояния системы"""
    # Проверяем ffmpeg
    ffmpeg_check = subprocess.run(['which', '/usr/bin/ffmpeg'], capture_output=True)
    
    # Проверяем yt-dlp
    ytdlp_check = subprocess.run(['which', 'yt-dlp'], capture_output=True)
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "/usr/bin/ffmpeg": ffmpeg_check.returncode == 0,
        "ffmpeg_path": ffmpeg_check.stdout.decode().strip() if ffmpeg_check.returncode == 0 else None,
        "yt-dlp": ytdlp_check.returncode == 0,
        "yt-dlp_path": ytdlp_check.stdout.decode().strip() if ytdlp_check.returncode == 0 else None,
        "transcriber": HAS_TRANSCRIBER,
        "google_sheets": HAS_GOOGLE_SHEETS,
        "google_sheets_connected": google_sheets_manager.client is not None if google_sheets_manager else False,
        "downloads_dir": os.path.exists(DOWNLOADS_DIR),
        "temp_files": len(os.listdir(TEMP_DIR)),
        "audio_files_cached": len(AUDIO_FILES)
    })

@app.route('/process', methods=['POST', 'OPTIONS'])
def process_video():
    """Обработка видео с сохранением в Google Sheets"""
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json(silent=True) or {}
        video_url = data.get('video_url', '')
        api_key = data.get('api_key', '')
        model = data.get('model', 'gemini-2.5-flash')
        language = data.get('language', 'ru')
        save_to_sheets = data.get('save_to_sheets', False)
        spreadsheet_id = data.get('spreadsheet_id', '')
        
        logger.info(f"Processing request: URL={video_url}, Model={model}, Lang={language}, Sheets={save_to_sheets}")
        
        if not video_url:
            return jsonify({"status": "error", "message": "URL видео обязателен"}), 400
            
        if not api_key:
            return jsonify({"status": "error", "message": "API ключ обязателен"}), 400
        
        # Генерируем уникальные имена файлов
        task_id = str(uuid.uuid4())
        video_path = os.path.join(TEMP_DIR, f"{task_id}.mp4")
        audio_path = os.path.join(DOWNLOADS_DIR, f"{task_id}.mp3")
        
        # Загружаем видео с помощью yt-dlp
        logger.info("Downloading video...")
        download_cmd = [
            "yt-dlp",
            "-f", "best[ext=mp4]/best",
            "-o", video_path,
            "--no-playlist",
            "--no-warnings",
            "--print-json",  # Получаем метаданные
            video_url
        ]
        
        result = subprocess.run(download_cmd, capture_output=True, text=True, timeout=120)
        
        # Парсим метаданные если доступны
        video_metadata = {}
        try:
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.startswith('{'):
                        video_metadata = json.loads(line)
                        break
        except:
            pass
        
        if result.returncode != 0:
            logger.error(f"Download failed: {result.stderr}")
            # Пробуем альтернативный метод без указания формата
            download_cmd = ["yt-dlp", "-o", video_path, "--no-playlist", video_url]
            result = subprocess.run(download_cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                return jsonify({"status": "error", "message": f"Не удалось загрузить видео: {result.stderr[:200]}"}), 500
        
        logger.info("Video downloaded successfully")
        
        # Извлекаем метаданные
        video_title = video_metadata.get('title', 'Unknown')
        video_author = video_metadata.get('uploader', 'Unknown')
        video_duration = video_metadata.get('duration', 0)
        video_platform = video_metadata.get('extractor', 'Unknown')
        
        # Извлекаем аудио с помощью ffmpeg
        logger.info("Extracting audio...")
        extract_cmd = [
            "/usr/bin/ffmpeg",
            "-i", video_path,
            "-vn",
            "-acodec", "libmp3lame",
            "-ab", "128k",
            "-ar", "44100",
            "-y",  # Перезаписывать если существует
            audio_path
        ]
        
        result = subprocess.run(extract_cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            logger.error(f"Audio extraction failed: {result.stderr}")
            return jsonify({"status": "error", "message": f"Не удалось извлечь аудио: {result.stderr[:200]}"}), 500
        
        logger.info("Audio extracted successfully")
        
        # Сохраняем путь к аудио
        AUDIO_FILES[task_id] = audio_path
        
        # Удаляем видео файл для экономии места
        try:
            os.remove(video_path)
            logger.info("Video file removed")
        except Exception as e:
            logger.warning(f"Could not remove video file: {e}")
        
        # Транскрибация
        transcript = ""
        summary = ""
        
        if HAS_TRANSCRIBER:
            logger.info("Starting transcription with Gemini...")
            try:
                # Пробуем полную транскрибацию
                transcript, summary = transcribe_with_gemini(
                    audio_path, 
                    api_key, 
                    model, 
                    language
                )
                logger.info("Transcription completed")
            except Exception as trans_error:
                logger.error(f"Transcription error: {trans_error}")
                # Используем упрощённую версию
                transcript, summary = transcribe_simple(
                    audio_path,
                    api_key,
                    model,
                    language
                )
        else:
            # Если модуль транскрибации недоступен
            transcript = f"[Транскрибация временно недоступна. Аудио успешно извлечено и сохранено.]"
            summary = f"Видео обработано. Аудио файл готов к скачиванию (ID: {task_id})"
        
        # Сохраняем в Google Sheets если нужно
        sheets_saved = False
        sheets_url = None
        
        if save_to_sheets and HAS_GOOGLE_SHEETS and google_sheets_manager:
            logger.info("Saving to Google Sheets...")
            
            # Если нет spreadsheet_id, создаем новую таблицу
            if not spreadsheet_id and google_sheets_manager.client:
                result = google_sheets_manager.create_spreadsheet(
                    f"TikTok Transcriptions {datetime.now().strftime('%Y-%m-%d')}"
                )
                if 'id' in result:
                    spreadsheet_id = result['id']
                    sheets_url = result.get('url', '')
                    logger.info(f"Created new spreadsheet: {spreadsheet_id}")
            
            # Открываем таблицу если есть ID
            if spreadsheet_id:
                if google_sheets_manager.open_spreadsheet(spreadsheet_id):
                    # Добавляем запись
                    record_data = {
                        'id': task_id,
                        'video_url': video_url,
                        'platform': video_platform,
                        'author': video_author,
                        'title': video_title,
                        'duration': f"{video_duration//60}:{video_duration%60:02d}" if video_duration else 'N/A',
                        'audio_file': f"http://158.180.56.74/download-audio/{task_id}",
                        'transcription': transcript[:1000] + '...' if len(transcript) > 1000 else transcript,
                        'model': model,
                        'language': language,
                        'status': 'completed'
                    }
                    
                    if google_sheets_manager.add_transcription(record_data):
                        sheets_saved = True
                        if not sheets_url:
                            sheets_url = google_sheets_manager.spreadsheet.url if google_sheets_manager.spreadsheet else None
                        logger.info("Successfully saved to Google Sheets")
                    else:
                        logger.warning("Failed to save to Google Sheets")
        
        logger.info(f"Processing complete. Audio ID: {task_id}")
        
        response = {
            "status": "completed",
            "message": "Обработка завершена",
            "transcript": transcript,
            "summary": summary,
            "audio_id": task_id,
            "model_used": model,
            "metadata": {
                "title": video_title,
                "author": video_author,
                "duration": video_duration,
                "platform": video_platform
            }
        }
        
        if sheets_saved:
            response["google_sheets"] = {
                "saved": True,
                "spreadsheet_id": spreadsheet_id,
                "url": sheets_url
            }
        
        return jsonify(response)
        
    except subprocess.TimeoutExpired:
        logger.error("Process timeout")
        return jsonify({"status": "error", "message": "Превышено время обработки"}), 500
    except Exception as e:
        logger.error(f"Error in /process: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/sheets/create', methods=['POST'])
def create_spreadsheet():
    """Создание новой Google таблицы"""
    if not HAS_GOOGLE_SHEETS or not google_sheets_manager or not google_sheets_manager.client:
        return jsonify({"status": "error", "message": "Google Sheets не настроен"}), 503
    
    data = request.get_json(silent=True) or {}
    title = data.get('title', f"TikTok Transcriptions {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    folder_id = data.get('folder_id', None)
    
    result = google_sheets_manager.create_spreadsheet(title, folder_id)
    
    if 'error' in result:
        return jsonify({"status": "error", "message": result['error']}), 500
    
    return jsonify({
        "status": "success",
        "spreadsheet": result
    })

@app.route('/sheets/list/<spreadsheet_id>')
def list_transcriptions(spreadsheet_id):
    """Получение списка транскрибаций из таблицы"""
    if not HAS_GOOGLE_SHEETS or not google_sheets_manager:
        return jsonify({"status": "error", "message": "Google Sheets не настроен"}), 503
    
    if google_sheets_manager.open_spreadsheet(spreadsheet_id):
        records = google_sheets_manager.get_all_transcriptions()
        return jsonify({
            "status": "success",
            "count": len(records),
            "records": records
        })
    else:
        return jsonify({"status": "error", "message": "Не удалось открыть таблицу"}), 404

@app.route('/sheets/stats/<spreadsheet_id>')
def get_sheets_statistics(spreadsheet_id):
    """Получение статистики из таблицы"""
    if not HAS_GOOGLE_SHEETS or not google_sheets_manager:
        return jsonify({"status": "error", "message": "Google Sheets не настроен"}), 503
    
    if google_sheets_manager.open_spreadsheet(spreadsheet_id):
        stats = google_sheets_manager.get_statistics()
        return jsonify({
            "status": "success",
            "statistics": stats
        })
    else:
        return jsonify({"status": "error", "message": "Не удалось открыть таблицу"}), 404

@app.route('/sheets/export/<spreadsheet_id>')
def export_to_excel(spreadsheet_id):
    """Экспорт таблицы в Excel"""
    if not HAS_GOOGLE_SHEETS or not google_sheets_manager:
        return jsonify({"status": "error", "message": "Google Sheets не настроен"}), 503
    
    if google_sheets_manager.open_spreadsheet(spreadsheet_id):
        filepath = google_sheets_manager.export_to_excel()
        if filepath:
            return send_from_directory(
                os.path.dirname(filepath),
                os.path.basename(filepath),
                as_attachment=True
            )
        else:
            return jsonify({"status": "error", "message": "Не удалось экспортировать"}), 500
    else:
        return jsonify({"status": "error", "message": "Не удалось открыть таблицу"}), 404

@app.route('/download-audio/<audio_id>')
def download_audio(audio_id):
    """Скачивание аудио"""
    if audio_id not in AUDIO_FILES:
        return jsonify({"status": "error", "message": "Аудио не найдено"}), 404
    
    audio_path = AUDIO_FILES[audio_id]
    if not os.path.exists(audio_path):
        return jsonify({"status": "error", "message": "Файл не существует"}), 404
    
    return send_from_directory(
        os.path.dirname(audio_path),
        os.path.basename(audio_path),
        as_attachment=True,
        download_name=f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
    )

@app.route('/history')
def history():
    """История транскрибаций"""
    # Показываем список обработанных файлов
    history_items = []
    for audio_id, path in AUDIO_FILES.items():
        if os.path.exists(path):
            size = os.path.getsize(path) / (1024 * 1024)  # В мегабайтах
            history_items.append({
                "id": audio_id,
                "filename": os.path.basename(path),
                "size_mb": round(size, 2),
                "exists": True
            })
    
    return jsonify({
        "status": "success",
        "count": len(history_items),
        "history": history_items
    })

# Обслуживание статических файлов
@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory(STATIC_DIR, path)

@app.route('/models')
def list_models():
    """Список доступных моделей Gemini"""
    models = [
        {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "description": "Продвинутое мышление и рассуждения"},
        {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "description": "Быстрая и умная"},
        {"id": "gemini-2.5-flash-lite", "name": "Gemini 2.5 Flash-Lite", "description": "Самая экономичная"},
        {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "description": "Стриминг и реальное время"},
        {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "description": "Классическая быстрая"},
        {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "description": "Классическая продвинутая"},
    ]
    return jsonify(models)

@app.route('/config')
def get_config():
    """Получение конфигурации приложения"""
    return jsonify({
        "has_transcriber": HAS_TRANSCRIBER,
        "has_google_sheets": HAS_GOOGLE_SHEETS,
        "google_sheets_connected": google_sheets_manager.client is not None if google_sheets_manager else False,
        "default_spreadsheet_id": os.environ.get('GOOGLE_SPREADSHEET_ID', ''),
        "server_url": "http://158.180.56.74"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)


# Admin endpoints for service management
@app.route('/admin/restart', methods=['POST'])
def admin_restart_service():
    """Restart the PM2 service"""
    try:
        import subprocess
        result = subprocess.run(
            ['pm2', 'restart', 'tiktok-transcriber'],
            capture_output=True,
            text=True,
            timeout=10
        )
        return jsonify({"status": "success", "message": "Service restarted"})
    except Exception as e:
        logger.error(f"Restart error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/admin/status', methods=['GET'])
def admin_service_status():
    """Get service status"""
    try:
        return jsonify({
            "status": "success", 
            "service": {
                "status": "online",
                "uptime": "N/A",
                "restarts": "N/A"
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

