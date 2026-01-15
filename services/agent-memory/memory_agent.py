#!/usr/bin/env python3
"""
Agent Memory System v1.0
Центральная система памяти для VM агентов
"""

import json
import sqlite3
import os
import hashlib
from datetime import datetime
from pathlib import Path

MEMORY_DIR = Path.home() / "agent-memory"
DB_PATH = MEMORY_DIR / "memory.db"
KNOWLEDGE_DIR = MEMORY_DIR / "knowledge"
HISTORY_FILE = MEMORY_DIR / "history" / "operations.jsonl"

class AgentMemory:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self._init_db()
        
    def _init_db(self):
        """Инициализация базы данных"""
        self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY,
                category TEXT,
                key TEXT,
                value TEXT,
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(category, key)
            );
            
            CREATE TABLE IF NOT EXISTS operations (
                id INTEGER PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                vm TEXT,
                action TEXT,
                command TEXT,
                result TEXT,
                success INTEGER
            );
            
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE,
                description TEXT,
                category TEXT,
                last_modified TIMESTAMP,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE VIRTUAL TABLE IF NOT EXISTS fts_knowledge USING fts5(
                category, key, value, tags
            );
        ''')
        self.conn.commit()
        
    def add_knowledge(self, category, key, value, tags=None):
        """Добавить знание в базу"""
        tags_str = json.dumps(tags or [])
        self.conn.execute('''
            INSERT OR REPLACE INTO knowledge (category, key, value, tags, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (category, key, json.dumps(value) if isinstance(value, (dict, list)) else value, tags_str))
        self.conn.commit()
        return {"status": "added", "category": category, "key": key}
        
    def search(self, query, category=None):
        """Поиск по базе знаний"""
        if category:
            cursor = self.conn.execute('''
                SELECT category, key, value, tags FROM knowledge 
                WHERE category = ? AND (key LIKE ? OR value LIKE ?)
            ''', (category, f'%{query}%', f'%{query}%'))
        else:
            cursor = self.conn.execute('''
                SELECT category, key, value, tags FROM knowledge 
                WHERE key LIKE ? OR value LIKE ?
            ''', (f'%{query}%', f'%{query}%'))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "category": row[0],
                "key": row[1],
                "value": row[2],
                "tags": json.loads(row[3]) if row[3] else []
            })
        return results
        
    def log_operation(self, vm, action, command, result, success=True):
        """Логировать операцию"""
        self.conn.execute('''
            INSERT INTO operations (vm, action, command, result, success)
            VALUES (?, ?, ?, ?, ?)
        ''', (vm, action, command, str(result)[:1000], 1 if success else 0))
        self.conn.commit()
        
    def get_history(self, vm=None, limit=20):
        """Получить историю операций"""
        if vm:
            cursor = self.conn.execute('''
                SELECT timestamp, vm, action, command, success FROM operations
                WHERE vm = ? ORDER BY timestamp DESC LIMIT ?
            ''', (vm, limit))
        else:
            cursor = self.conn.execute('''
                SELECT timestamp, vm, action, command, success FROM operations
                ORDER BY timestamp DESC LIMIT ?
            ''', (limit,))
        return [{"timestamp": r[0], "vm": r[1], "action": r[2], "command": r[3], "success": bool(r[4])} 
                for r in cursor.fetchall()]
                
    def index_file(self, path, description, category):
        """Индексировать файл"""
        path = str(Path(path).expanduser())
        mtime = os.path.getmtime(path) if os.path.exists(path) else None
        self.conn.execute('''
            INSERT OR REPLACE INTO files (path, description, category, last_modified)
            VALUES (?, ?, ?, ?)
        ''', (path, description, category, mtime))
        self.conn.commit()
        
    def find_file(self, query):
        """Найти файл по описанию или пути"""
        cursor = self.conn.execute('''
            SELECT path, description, category FROM files
            WHERE path LIKE ? OR description LIKE ?
        ''', (f'%{query}%', f'%{query}%'))
        return [{"path": r[0], "description": r[1], "category": r[2]} for r in cursor.fetchall()]
        
    def load_json_knowledge(self):
        """Загрузить знания из JSON файлов"""
        for json_file in KNOWLEDGE_DIR.glob("*.json"):
            category = json_file.stem
            with open(json_file) as f:
                data = json.load(f)
                self._index_dict(category, data)
                
    def _index_dict(self, category, data, prefix=""):
        """Рекурсивно индексировать словарь"""
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                self._index_dict(category, value, full_key)
            else:
                self.add_knowledge(category, full_key, value)

    def get_path(self, what):
        """Быстрый поиск пути"""
        results = self.search(what)
        for r in results:
            if 'path' in r['key'].lower() or '/' in str(r['value']):
                return r['value']
        return None
        
    def summary(self):
        """Сводка по базе"""
        counts = {}
        for table in ['knowledge', 'operations', 'files']:
            cursor = self.conn.execute(f'SELECT COUNT(*) FROM {table}')
            counts[table] = cursor.fetchone()[0]
        return counts


def cli():
    """CLI интерфейс"""
    import sys
    mem = AgentMemory()
    
    if len(sys.argv) < 2:
        print("Usage: memory_agent.py <command> [args]")
        print("Commands: search, add, history, index, path, summary, load")
        return
        
    cmd = sys.argv[1]
    
    if cmd == "search" and len(sys.argv) > 2:
        results = mem.search(" ".join(sys.argv[2:]))
        print(json.dumps(results, indent=2, ensure_ascii=False))
        
    elif cmd == "history":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        results = mem.get_history(limit=limit)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        
    elif cmd == "path" and len(sys.argv) > 2:
        result = mem.get_path(" ".join(sys.argv[2:]))
        print(result or "Not found")
        
    elif cmd == "summary":
        print(json.dumps(mem.summary(), indent=2))
        
    elif cmd == "load":
        mem.load_json_knowledge()
        print("✅ Knowledge loaded from JSON files")
        print(json.dumps(mem.summary(), indent=2))
        
    elif cmd == "add" and len(sys.argv) >= 5:
        category, key, value = sys.argv[2], sys.argv[3], " ".join(sys.argv[4:])
        result = mem.add_knowledge(category, key, value)
        print(json.dumps(result))
        
    else:
        print(f"Unknown command or missing args: {cmd}")

if __name__ == "__main__":
    cli()
