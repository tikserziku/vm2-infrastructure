#!/usr/bin/env python3
"""
Veo Video Generation API Service
Генерация видео через Gemini Veo 3.1
Документация: https://github.com/googleapis/python-genai
"""

from flask import Flask, request, jsonify
from google import genai
from google.genai import types
import base64
import time
import logging
import requests

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API Key
API_KEY = "AIzaSyAXlZOVd0_igKYnNaQqJtBfQ4Ch-QGu9cc"

# Модели Veo
VEO_FAST = "veo-3.0-fast-generate-001"  # Veo 3.0 fast
VEO_31 = "veo-3.1-generate-preview"      # Veo 3.1 preview

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "veo-video-api"})

@app.route('/generate', methods=['POST'])
def generate_video():
    """
    Генерация видео
    
    Body JSON:
    {
        "prompt": "описание видео",
        "image_base64": "base64 изображения (опционально)",
        "image_mime": "image/jpeg",
        "model": "fast" или "full",
        "aspect_ratio": "16:9" или "9:16",
        "duration_seconds": 5-8
    }
    """
    try:
        data = request.json
        prompt = data.get('prompt', '')
        image_base64 = data.get('image_base64')
        image_mime = data.get('image_mime', 'image/jpeg')
        model_type = data.get('model', 'fast')
        aspect_ratio = data.get('aspect_ratio', '16:9')
        duration = data.get('duration_seconds', 5)
        
        logger.info(f"Video request: prompt='{prompt[:50] if prompt else 'none'}...', has_image={bool(image_base64)}")
        
        # Выбор модели
        model = VEO_FAST if model_type == 'fast' else VEO_31
        
        # Инициализация клиента
        client = genai.Client(api_key=API_KEY)
        
        # Конфигурация по документации
        config = types.GenerateVideosConfig(
            number_of_videos=1,
            duration_seconds=5,
            aspect_ratio=aspect_ratio,
            enhance_prompt=True,
            person_generation='allow_adult',
        )
        
        # Параметры генерации
        kwargs = {
            "model": model,
            "config": config,
        }
        
        # Добавляем промпт
        if prompt:
            kwargs["prompt"] = prompt
        
        # Добавляем изображение если есть (Image-to-Video)
        if image_base64:
            # Декодируем base64 в bytes
            image_bytes = base64.b64decode(image_base64)
            # Создаём объект Image
            kwargs["image"] = types.Image(
                image_bytes=image_bytes,
                mime_type=image_mime,
            )
            logger.info(f"Using image as start frame: {len(image_bytes)} bytes, mime: {image_mime}")
        
        logger.info(f"Submitting video generation: model={model}")
        
        # Запуск генерации
        operation = client.models.generate_videos(**kwargs)
        logger.info(f"Operation started: {operation.name if hasattr(operation, 'name') else operation}")
        
        # Ожидание завершения (polling) - ПРАВИЛЬНЫЙ метод из документации!
        max_wait = 300  # 5 минут максимум
        wait_time = 0
        poll_interval = 20  # 20 секунд как в документации
        
        while not operation.done and wait_time < max_wait:
            time.sleep(poll_interval)
            wait_time += poll_interval
            logger.info(f"...Generating video ({wait_time}s)...")
            # Правильный метод из документации
            operation = client.operations.get(operation)
        
        if not operation.done:
            return jsonify({"error": "Video generation timeout (5 min)"}), 504
        
        # Проверяем на ошибку
        if hasattr(operation, 'error') and operation.error:
            logger.error(f"Operation error: {operation.error}")
            return jsonify({"error": str(operation.error)}), 500
        
        # Получаем результат
        if operation.response:
            generated_videos = operation.response.generated_videos
            
            if not generated_videos or len(generated_videos) == 0:
                # Проверяем фильтрацию RAI
                if hasattr(operation.response, 'rai_media_filtered_count'):
                    filtered = operation.response.rai_media_filtered_count
                    reasons = operation.response.rai_media_filtered_reasons
                    if filtered > 0:
                        return jsonify({
                            "error": f"Video filtered by safety: {reasons}"
                        }), 400
                return jsonify({"error": "No videos were generated"}), 500
            
            first_video = generated_videos[0]
            video_obj = first_video.video
            
            if not video_obj or not video_obj.uri:
                return jsonify({"error": "Generated video is missing URI"}), 500
            
            video_uri = video_obj.uri
            logger.info(f"Video generated! URI: {video_uri[:80]}...")
            
            # Скачиваем видео
            # URI уже содержит параметры, добавляем API key
            if '?' in video_uri:
                video_url = f"{video_uri}&key={API_KEY}"
            else:
                video_url = f"{video_uri}?key={API_KEY}"
                
            response = requests.get(video_url, timeout=60)
            
            if response.status_code != 200:
                logger.error(f"Failed to download video: {response.status_code} - {response.text[:200]}")
                return jsonify({"error": f"Failed to download video: {response.status_code}"}), 500
            
            # Конвертируем в base64
            video_base64 = base64.b64encode(response.content).decode('utf-8')
            video_size = len(response.content)
            
            logger.info(f"Video downloaded: {video_size} bytes ({video_size/1024/1024:.1f} MB)")
            
            return jsonify({
                "success": True,
                "video_base64": video_base64,
                "video_size": video_size,
                "mime_type": "video/mp4",
            })
        else:
            logger.error(f"Operation completed but no response: {operation}")
            return jsonify({"error": "Video generation failed - no response"}), 500
            
    except Exception as e:
        logger.error(f"Error generating video: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    logger.info("Starting Veo Video API on port 5681...")
    app.run(host='0.0.0.0', port=5681, debug=False)
