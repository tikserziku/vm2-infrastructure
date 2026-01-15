#!/usr/bin/env python3
from flask import Flask, jsonify, request, send_from_directory, render_template_string
from flask_cors import CORS
import os
import logging
import subprocess
import uuid
import shutil
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Папки для хранения файлов
DOWNLOADS_DIR = "downloads"
TEMP_DIR = "temp"
LOGS_DIR = "logs"
STATIC_DIR = "static"

# Создаём необходимые директории
for dir_path in [DOWNLOADS_DIR, TEMP_DIR, LOGS_DIR]:
    os.makedirs(dir_path, exist_ok=True)

# Словарь для хранения путей к файлам
AUDIO_FILES = {}

# Импортируем модуль транскрибации
try:
    from transcriber import transcribe_with_gemini, transcribe_simple
    HAS_TRANSCRIBER = True
    logger.info("Transcriber module loaded successfully")
except ImportError as e:
    logger.warning(f"Transcriber module not available: {e}")
    HAS_TRANSCRIBER = False

@app.route('/')
def home():
    """Главная страница с интерфейсом"""
    html_path = os.path.join(STATIC_DIR, 'html', 'index.html')
    if os.path.exists(html_path):
        return send_from_directory(os.path.join(STATIC_DIR, 'html'), 'index.html')
    else:
        # Запасной вариант
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>TikTok Transcriber</title>
            <meta charset="utf-8">
            <style>
                body { font-family: Arial; max-width: 800px; margin: 50px auto; padding: 20px; }
                h1 { color: #333; }
                .status { background: #e8f5e9; padding: 15px; border-radius: 5px; }
            </style>
        </head>
        <body>
            <h1>🎥 TikTok Transcriber API</h1>
            <div class="status">
                <h3>✅ Сервер работает на Oracle VM</h3>
                <p>Откройте страницу с полным интерфейсом</p>
            </div>
        </body>
        </html>
        '''

@app.route('/fixed')
def fixed_page():
    """Альтернативный маршрут для интерфейса"""
    return home()

@app.route('/health')
def health():
    """Проверка состояния"""
    ffmpeg_check = subprocess.run(['which', 'ffmpeg'], capture_output=True)
    ytdlp_check = subprocess.run(['which', 'yt-dlp'], capture_output=True)
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "/usr/bin/ffmpeg": ffmpeg_check.returncode == 0,
        "ffmpeg_path": ffmpeg_check.stdout.decode().strip() if ffmpeg_check.returncode == 0 else None,
        "yt-dlp": ytdlp_check.returncode == 0,
        "yt-dlp_path": ytdlp_check.stdout.decode().strip() if ytdlp_check.returncode == 0 else None,
        "transcriber": HAS_TRANSCRIBER,
        "downloads_dir": os.path.exists(DOWNLOADS_DIR),
        "temp_files": len(os.listdir(TEMP_DIR)),
        "audio_files_cached": len(AUDIO_FILES)
    })

@app.route('/process', methods=['POST', 'OPTIONS'])
def process_video():
    """Обработка видео"""
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json(silent=True) or {}
        video_url = data.get('video_url', '')
        api_key = data.get('api_key', '')
        model = data.get('model', 'gemini-2.5-flash')
        language = data.get('language', 'ru')
        
        logger.info(f"Processing request: URL={video_url}, Model={model}, Lang={language}")
        
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
            video_url
        ]
        
        result = subprocess.run(download_cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.error(f"Download failed: {result.stderr}")
            # Пробуем альтернативный метод без указания формата
            download_cmd = ["yt-dlp", "-o", video_path, "--no-playlist", video_url]
            result = subprocess.run(download_cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                return jsonify({"status": "error", "message": f"Не удалось загрузить видео: {result.stderr[:200]}"}), 500
        
        logger.info("Video downloaded successfully")
        
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
        
        logger.info(f"Processing complete. Audio ID: {task_id}")
        
        return jsonify({
            "status": "completed",
            "message": "Обработка завершена",
            "transcript": transcript,
            "summary": summary,
            "audio_id": task_id,
            "model_used": model
        })
        
    except subprocess.TimeoutExpired:
        logger.error("Process timeout")
        return jsonify({"status": "error", "message": "Превышено время обработки"}), 500
    except Exception as e:
        logger.error(f"Error in /process: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

