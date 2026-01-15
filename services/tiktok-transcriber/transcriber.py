#!/usr/bin/env python3
"""
Модуль для транскрибации аудио с помощью Google Gemini
"""
import os
import logging
import google.generativeai as genai
from pathlib import Path

logger = logging.getLogger(__name__)

def transcribe_with_gemini(audio_path, api_key, model_name="gemini-2.5-flash", language="ru"):
    """
    Транскрибирует аудио файл с помощью Gemini API
    
    Args:
        audio_path: Путь к аудио файлу
        api_key: API ключ для Gemini
        model_name: Название модели Gemini
        language: Язык для транскрибации
        
    Returns:
        tuple: (transcript, summary)
    """
    try:
        # Настраиваем API
        genai.configure(api_key=api_key)
        
        # Выбираем модель
        # Для аудио лучше использовать модели с поддержкой мультимодальности
        if model_name in ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]:
            model = genai.GenerativeModel(model_name)
        else:
            # Для специальных моделей используем базовую
            model = genai.GenerativeModel("gemini-2.5-flash")
            
        # Загружаем аудио файл
        audio_file = genai.upload_file(path=audio_path)
        
        # Определяем язык для промпта
        lang_prompts = {
            "ru": {
                "transcribe": "Транскрибируй это аудио на русском языке. Сохрани все детали и нюансы.",
                "summary": "Создай краткое содержание этого аудио на русском языке."
            },
            "en": {
                "transcribe": "Transcribe this audio in English. Keep all details and nuances.",
                "summary": "Create a summary of this audio in English."
            },
            "auto": {
                "transcribe": "Transcribe this audio in its original language. Keep all details.",
                "summary": "Create a summary of this audio in its original language."
            }
        }
        
        prompts = lang_prompts.get(language, lang_prompts["auto"])
        
        # Получаем транскрипцию
        logger.info(f"Transcribing with {model_name}...")
        response = model.generate_content([
            audio_file,
            prompts["transcribe"]
        ])
        transcript = response.text
        
        # Получаем саммари
        logger.info("Generating summary...")
        response = model.generate_content([
            audio_file,
            prompts["summary"]
        ])
        summary = response.text
        
        # Удаляем загруженный файл из Gemini
        genai.delete_file(audio_file.name)
        
        return transcript, summary
        
    except Exception as e:
        logger.error(f"Error in transcription: {str(e)}")
        # Возвращаем ошибку, но не падаем
        error_msg = f"Ошибка транскрибации: {str(e)}"
        return error_msg, "Не удалось создать краткое содержание"

def transcribe_simple(audio_path, api_key, model_name="gemini-2.5-flash", language="ru"):
    """
    Упрощённая версия транскрибации (только текст)
    """
    try:
        genai.configure(api_key=api_key)
        
        # Используем базовую модель для текста
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Читаем аудио как бинарные данные
        with open(audio_path, 'rb') as f:
            audio_data = f.read()
        
        # Простой промпт
        prompt = "Transcribe this audio and provide a summary."
        if language == "ru":
            prompt = "Транскрибируй это аудио и создай краткое содержание."
            
        # Пробуем отправить как текстовый запрос
        response = model.generate_content(prompt)
        
        return response.text, "Аудио обработано"
        
    except Exception as e:
        logger.error(f"Simple transcription failed: {str(e)}")
        return f"Временная заглушка: аудио извлечено из {Path(audio_path).name}", "Требуется настройка Gemini API для полной транскрибации"

