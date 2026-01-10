import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from config import Config

class CommandHistory:
    def __init__(self):
        self.history_file = "logs/command_history.json"
        self.history = []
        self.load_history()
        
    def load_history(self):
        """Загрузка истории команд"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.history = []
            
    def save_history(self):
        """Сохранение истории команд"""
        try:
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка сохранения истории: {e}")
            
    def add_command(self, user_id: int, command: str, success: bool = True):
        """Добавить команду в историю"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'command': command,
            'success': success
        }
        
        self.history.append(entry)
        
        # Ограничиваем размер истории
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
            
        self.save_history()
        
    def search_history(self, query: str, user_id: int = None, limit: int = 10) -> List[Dict]:
        """Поиск по истории команд"""
        results = []
        
        for entry in reversed(self.history):
            if user_id and entry['user_id'] != user_id:
                continue
                
            if query.lower() in entry['command'].lower():
                results.append(entry)
                
            if len(results) >= limit:
                break
                
        return results
        
    def get_recent_commands(self, user_id: int = None, limit: int = 20) -> List[Dict]:
        """Получить последние команды"""
        recent = []
        
        for entry in reversed(self.history):
            if user_id and entry['user_id'] != user_id:
                continue
                
            recent.append(entry)
            
            if len(recent) >= limit:
                break
                
        return recent
        
    def get_user_stats(self, user_id: int) -> Dict:
        """Получить статистику пользователя"""
        user_commands = [cmd for cmd in self.history if cmd['user_id'] == user_id]
        
        if not user_commands:
            return {'total': 0, 'success': 0, 'failed': 0}
            
        total = len(user_commands)
        success = sum(1 for cmd in user_commands if cmd['success'])
        failed = total - success
        
        return {
            'total': total,
            'success': success,
            'failed': failed,
            'success_rate': (success / total) * 100 if total > 0 else 0
        }
        
    def get_command_frequency(self, user_id: int = None) -> Dict[str, int]:
        """Получить частоту использования команд"""
        frequency = {}
        
        for entry in self.history:
            if user_id and entry['user_id'] != user_id:
                continue
                
            # Берем первое слово команды
            cmd = entry['command'].split()[0] if entry['command'] else 'unknown'
            frequency[cmd] = frequency.get(cmd, 0) + 1
            
        return dict(sorted(frequency.items(), key=lambda x: x[1], reverse=True))
        
    def clear_history(self, user_id: int = None):
        """Очистить историю"""
        if user_id:
            self.history = [cmd for cmd in self.history if cmd['user_id'] != user_id]
        else:
            self.history = []
            
        self.save_history()

# Глобальный экземпляр истории
command_history = CommandHistory()