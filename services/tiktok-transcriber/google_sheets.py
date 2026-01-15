#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Google Sheets Integration Module for TikTok Transcriber
Модуль для работы с Google Таблицами
"""

import os
import json
import base64
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import gspread
from google.oauth2 import service_account
from google.auth.exceptions import GoogleAuthError
import pandas as pd

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GoogleSheetsManager:
    """Менеджер для работы с Google Sheets"""
    
    def __init__(self, credentials_path: Optional[str] = None):
        """
        Инициализация менеджера
        
        Args:
            credentials_path: Путь к файлу credentials.json или None для использования переменных окружения
        """
        self.client = None
        self.credentials = None
        self.spreadsheet = None
        self.worksheet = None
        
        # Попытка получить credentials
        try:
            self.credentials = self._get_credentials(credentials_path)
            if self.credentials:
                self.client = gspread.authorize(self.credentials)
                logger.info("✅ Google Sheets client authorized successfully")
            else:
                logger.warning("⚠️ No Google Sheets credentials found")
        except Exception as e:
            logger.error(f"❌ Error initializing Google Sheets: {e}")
    
    def _get_credentials(self, credentials_path: Optional[str] = None):
        """
        Получение credentials из файла или переменных окружения
        
        Returns:
            service_account.Credentials или None
        """
        # Попытка 1: Использовать переданный путь к файлу
        if credentials_path and os.path.exists(credentials_path):
            try:
                return service_account.Credentials.from_service_account_file(
                    credentials_path,
                    scopes=['https://www.googleapis.com/auth/spreadsheets',
                           'https://www.googleapis.com/auth/drive']
                )
            except Exception as e:
                logger.error(f"Error loading credentials from file: {e}")
        
        # Попытка 2: Использовать base64 из переменной окружения
        creds_base64 = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_BASE64')
        if creds_base64:
            try:
                creds_json = base64.b64decode(creds_base64).decode('utf-8')
                creds_dict = json.loads(creds_json)
                return service_account.Credentials.from_service_account_info(
                    creds_dict,
                    scopes=['https://www.googleapis.com/auth/spreadsheets',
                           'https://www.googleapis.com/auth/drive']
                )
            except Exception as e:
                logger.error(f"Error loading credentials from base64: {e}")
        
        # Попытка 3: Проверить стандартные пути
        standard_paths = [
            '/home/ubuntu/tiktok-transcriber/credentials.json',
            './credentials.json',
            '../credentials.json'
        ]
        
        for path in standard_paths:
            if os.path.exists(path):
                try:
                    return service_account.Credentials.from_service_account_file(
                        path,
                        scopes=['https://www.googleapis.com/auth/spreadsheets',
                               'https://www.googleapis.com/auth/drive']
                    )
                except Exception as e:
                    logger.error(f"Error loading credentials from {path}: {e}")
        
        return None
    
    def create_spreadsheet(self, title: str, folder_id: Optional[str] = None) -> Dict[str, str]:
        """
        Создание новой Google таблицы
        
        Args:
            title: Название таблицы
            folder_id: ID папки в Google Drive (опционально)
        
        Returns:
            Словарь с информацией о созданной таблице
        """
        if not self.client:
            return {"error": "Google Sheets client not initialized"}
        
        try:
            # Создаем таблицу
            spreadsheet = self.client.create(title)
            
            # Если указана папка, перемещаем туда
            if folder_id:
                spreadsheet.client.drive.move_file(spreadsheet.id, folder_id)
            
            # Делаем таблицу доступной по ссылке
            spreadsheet.share('', perm_type='anyone', role='reader', with_link=True)
            
            self.spreadsheet = spreadsheet
            self.worksheet = spreadsheet.sheet1
            
            # Настраиваем заголовки
            headers = [
                'ID', 'Timestamp', 'Video URL', 'Platform', 
                'Author', 'Title', 'Duration', 'Audio File',
                'Transcription', 'Model Used', 'Language', 'Status'
            ]
            self.worksheet.update('A1:L1', [headers])
            
            # Форматируем заголовки
            self.worksheet.format('A1:L1', {
                "backgroundColor": {"red": 0.2, "green": 0.4, "blue": 0.8},
                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                "horizontalAlignment": "CENTER"
            })
            
            return {
                "id": spreadsheet.id,
                "url": spreadsheet.url,
                "title": title,
                "message": f"✅ Spreadsheet '{title}' created successfully"
            }
            
        except Exception as e:
            logger.error(f"Error creating spreadsheet: {e}")
            return {"error": str(e)}
    
    def open_spreadsheet(self, spreadsheet_id: str) -> bool:
        """
        Открытие существующей таблицы по ID
        
        Args:
            spreadsheet_id: ID Google таблицы
        
        Returns:
            True если успешно, False иначе
        """
        if not self.client:
            return False
        
        try:
            self.spreadsheet = self.client.open_by_key(spreadsheet_id)
            self.worksheet = self.spreadsheet.sheet1
            logger.info(f"✅ Opened spreadsheet: {self.spreadsheet.title}")
            return True
        except Exception as e:
            logger.error(f"Error opening spreadsheet: {e}")
            return False
    
    def add_transcription(self, data: Dict[str, Any]) -> bool:
        """
        Добавление новой записи о транскрибации
        
        Args:
            data: Словарь с данными о транскрибации
        
        Returns:
            True если успешно добавлено
        """
        if not self.worksheet:
            logger.error("No worksheet opened")
            return False
        
        try:
            # Подготавливаем данные для записи
            row_data = [
                data.get('id', ''),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                data.get('video_url', ''),
                data.get('platform', 'Unknown'),
                data.get('author', ''),
                data.get('title', ''),
                data.get('duration', ''),
                data.get('audio_file', ''),
                data.get('transcription', ''),
                data.get('model', 'gemini-2.0-flash'),
                data.get('language', 'auto'),
                data.get('status', 'completed')
            ]
            
            # Добавляем строку
            self.worksheet.append_row(row_data)
            
            # Автоподстройка ширины колонок
            self.worksheet.columns_auto_resize(0, 11)
            
            logger.info(f"✅ Added transcription record for: {data.get('title', 'Unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding transcription: {e}")
            return False
    
    def get_all_transcriptions(self) -> List[Dict[str, Any]]:
        """
        Получение всех записей из таблицы
        
        Returns:
            Список словарей с данными
        """
        if not self.worksheet:
            return []
        
        try:
            # Получаем все данные
            records = self.worksheet.get_all_records()
            logger.info(f"✅ Retrieved {len(records)} transcription records")
            return records
        except Exception as e:
            logger.error(f"Error getting transcriptions: {e}")
            return []
    
    def update_transcription_status(self, record_id: str, status: str, error_msg: str = "") -> bool:
        """
        Обновление статуса транскрибации
        
        Args:
            record_id: ID записи
            status: Новый статус
            error_msg: Сообщение об ошибке (если есть)
        
        Returns:
            True если успешно обновлено
        """
        if not self.worksheet:
            return False
        
        try:
            # Находим строку с нужным ID
            cell = self.worksheet.find(record_id)
            if cell:
                row_num = cell.row
                # Обновляем статус (колонка L)
                self.worksheet.update(f'L{row_num}', status)
                
                # Если есть ошибка, добавляем в колонку M
                if error_msg:
                    self.worksheet.update(f'M{row_num}', error_msg)
                
                logger.info(f"✅ Updated status for record {record_id}: {status}")
                return True
            else:
                logger.warning(f"Record {record_id} not found")
                return False
                
        except Exception as e:
            logger.error(f"Error updating status: {e}")
            return False
    
    def export_to_excel(self, output_path: str = '/home/ubuntu/tiktok-transcriber/exports/') -> Optional[str]:
        """
        Экспорт данных в Excel файл
        
        Args:
            output_path: Путь для сохранения файла
        
        Returns:
            Путь к созданному файлу или None
        """
        if not self.worksheet:
            return None
        
        try:
            # Создаем папку если не существует
            os.makedirs(output_path, exist_ok=True)
            
            # Получаем данные
            data = self.get_all_transcriptions()
            if not data:
                logger.warning("No data to export")
                return None
            
            # Создаем DataFrame
            df = pd.DataFrame(data)
            
            # Генерируем имя файла
            filename = f"transcriptions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            filepath = os.path.join(output_path, filename)
            
            # Сохраняем в Excel
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Transcriptions', index=False)
                
                # Форматируем
                worksheet = writer.sheets['Transcriptions']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            logger.info(f"✅ Exported to Excel: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error exporting to Excel: {e}")
            return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Получение статистики по транскрибациям
        
        Returns:
            Словарь со статистикой
        """
        if not self.worksheet:
            return {}
        
        try:
            data = self.get_all_transcriptions()
            if not data:
                return {"total": 0}
            
            df = pd.DataFrame(data)
            
            stats = {
                "total": len(df),
                "platforms": df['Platform'].value_counts().to_dict() if 'Platform' in df else {},
                "models": df['Model Used'].value_counts().to_dict() if 'Model Used' in df else {},
                "languages": df['Language'].value_counts().to_dict() if 'Language' in df else {},
                "statuses": df['Status'].value_counts().to_dict() if 'Status' in df else {},
                "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}


# Вспомогательные функции для интеграции с основным приложением
def init_google_sheets(spreadsheet_id: Optional[str] = None) -> Optional[GoogleSheetsManager]:
    """
    Инициализация менеджера Google Sheets
    
    Args:
        spreadsheet_id: ID таблицы для открытия (опционально)
    
    Returns:
        Экземпляр GoogleSheetsManager или None
    """
    try:
        manager = GoogleSheetsManager()
        
        # Если передан ID, открываем таблицу
        if spreadsheet_id:
            if manager.open_spreadsheet(spreadsheet_id):
                return manager
            else:
                logger.warning(f"Could not open spreadsheet: {spreadsheet_id}")
        
        # Если ID из переменной окружения
        env_spreadsheet_id = os.environ.get('GOOGLE_SPREADSHEET_ID')
        if env_spreadsheet_id and not spreadsheet_id:
            if manager.open_spreadsheet(env_spreadsheet_id):
                return manager
        
        return manager
        
    except Exception as e:
        logger.error(f"Error initializing Google Sheets: {e}")
        return None


if __name__ == "__main__":
    # Тестирование модуля
    print("🧪 Testing Google Sheets Module...")
    
    manager = init_google_sheets()
    if manager and manager.client:
        print("✅ Google Sheets client initialized successfully")
        
        # Тест создания таблицы
        # result = manager.create_spreadsheet("TikTok Transcriber Test")
        # print(f"Created spreadsheet: {result}")
        
        # Тест добавления записи
        # test_data = {
        #     'id': 'test_001',
        #     'video_url': 'https://example.com/video',
        #     'title': 'Test Video',
        #     'transcription': 'This is a test transcription'
        # }
        # manager.add_transcription(test_data)
        
    else:
        print("❌ Failed to initialize Google Sheets client")
        print("Please check credentials configuration")

