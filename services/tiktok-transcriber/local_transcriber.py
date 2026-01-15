#!/usr/bin/env python3
"""
Local Transcriber - Transcription using Gemini API
"""

import google.generativeai as genai
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def transcribe_with_gemini_2_5(audio_path, api_key, language='ru'):
    """
    Transcribe audio using Gemini 2.5 Flash
    
    Args:
        audio_path: Path to audio file
        api_key: Gemini API key
        language: Target language (ru, en, auto)
    
    Returns:
        tuple: (transcript, summary)
    """
    logger.info(f"Starting transcription with Gemini 2.5 Flash...")
    
    # Configure API
    genai.configure(api_key=api_key)
    
    # Upload file
    audio_file = Path(audio_path)
    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    
    logger.info(f"Uploading audio file: {audio_file.name}")
    uploaded_file = genai.upload_file(str(audio_file))
    
    # Wait for processing
    import time
    while uploaded_file.state.name == "PROCESSING":
        time.sleep(2)
        uploaded_file = genai.get_file(uploaded_file.name)
    
    if uploaded_file.state.name == "FAILED":
        raise Exception(f"File processing failed: {uploaded_file.state.name}")
    
    logger.info("File uploaded successfully, starting transcription...")
    
    # Create model
    model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
    
    # Language instructions
    lang_instruction = {
        'ru': 'на русском языке',
        'en': 'in English',
        'auto': 'на языке оригинала'
    }.get(language, 'на русском языке')
    
    # Transcription prompt
    transcription_prompt = f"""Прослушай это аудио и выполни транскрибацию {lang_instruction}.

Правила:
1. Точная транскрибация всех слов
2. Сохраняй паузы как новые абзацы
3. Не добавляй ничего от себя
4. Исправляй очевидные оговорки

Выдай только текст транскрибации, без комментариев."""

    # Get transcription
    response = model.generate_content([uploaded_file, transcription_prompt])
    transcript = response.text.strip()
    
    logger.info(f"Transcription complete: {len(transcript)} characters")
    
    # Summary prompt
    summary_prompt = f"""На основе этой транскрибации создай краткое саммари {lang_instruction}:

{transcript}

Саммари должно быть:
- 3-5 предложений
- Содержать основные тезисы
- Быть информативным"""

    # Get summary
    summary_response = model.generate_content(summary_prompt)
    summary = summary_response.text.strip()
    
    logger.info(f"Summary complete: {len(summary)} characters")
    
    # Cleanup
    try:
        genai.delete_file(uploaded_file.name)
    except:
        pass
    
    return transcript, summary


def transcribe_simple(audio_path, api_key, model_name='gemini-2.5-flash', language='ru'):
    """Simple transcription wrapper"""
    return transcribe_with_gemini_2_5(audio_path, api_key, language)


if __name__ == "__main__":
    print("Local Transcriber module loaded successfully")

