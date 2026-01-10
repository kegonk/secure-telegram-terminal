import json
import time
from datetime import datetime
from typing import Dict, Any
from config import Config
from logger import bot_logger

class MetricsCollector:
    def __init__(self):
        self.metrics = {
            'commands_executed': 0,
            'commands_failed': 0,
            'security_blocks': 0,
            'uptime_start': time.time(),
            'last_activity': None,
            'user_activity': {},
            'command_types': {},
            'errors': []
        }
        self.load_metrics()
        
    def load_metrics(self):
        """Загрузка метрик из файла"""
        if not Config.METRICS_ENABLED:
            return
            
        try:
            with open(Config.METRICS_FILE, 'r') as f:
                saved_metrics = json.load(f)
                self.metrics.update(saved_metrics)
        except (FileNotFoundError, json.JSONDecodeError):
            bot_logger.debug("Метрики не найдены, используем новые")
            
    def save_metrics(self):
        """Сохранение метрик в файл"""
        if not Config.METRICS_ENABLED:
            return
            
        try:
            import os
            os.makedirs(os.path.dirname(Config.METRICS_FILE), exist_ok=True)
            with open(Config.METRICS_FILE, 'w') as f:
                json.dump(self.metrics, f, indent=2, default=str)
        except Exception as e:
            bot_logger.error(f"Ошибка сохранения метрик: {e}")
            
    def increment_command_executed(self, user_id: int, command: str):
        """Увеличить счетчик выполненных команд"""
        self.metrics['commands_executed'] += 1
        self.metrics['last_activity'] = datetime.now().isoformat()
        
        # Активность пользователя
        if str(user_id) not in self.metrics['user_activity']:
            self.metrics['user_activity'][str(user_id)] = 0
        self.metrics['user_activity'][str(user_id)] += 1
        
        # Типы команд
        cmd_type = command.split()[0] if command else 'unknown'
        if cmd_type not in self.metrics['command_types']:
            self.metrics['command_types'][cmd_type] = 0
        self.metrics['command_types'][cmd_type] += 1
        
        self.save_metrics()
        
    def increment_command_failed(self, user_id: int, command: str, error: str):
        """Увеличить счетчик неудачных команд"""
        self.metrics['commands_failed'] += 1
        self.metrics['errors'].append({
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'command': command,
            'error': error
        })
        
        # Ограничиваем количество сохраненных ошибок
        if len(self.metrics['errors']) > 100:
            self.metrics['errors'] = self.metrics['errors'][-100:]
            
        self.save_metrics()
        
    def increment_security_block(self, user_id: int, command: str, reason: str):
        """Увеличить счетчик блокировок безопасности"""
        self.metrics['security_blocks'] += 1
        bot_logger.log_security_event(user_id, 'COMMAND_BLOCKED', f"{command} - {reason}")
        self.save_metrics()
        
    def get_uptime(self) -> str:
        """Получить время работы"""
        uptime_seconds = time.time() - self.metrics['uptime_start']
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        return f"{hours}h {minutes}m"
        
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику"""
        return {
            'uptime': self.get_uptime(),
            'commands_executed': self.metrics['commands_executed'],
            'commands_failed': self.metrics['commands_failed'],
            'security_blocks': self.metrics['security_blocks'],
            'success_rate': self._calculate_success_rate(),
            'last_activity': self.metrics['last_activity'],
            'active_users': len(self.metrics['user_activity']),
            'top_commands': self._get_top_commands()
        }
        
    def _calculate_success_rate(self) -> float:
        """Вычислить процент успешных команд"""
        total = self.metrics['commands_executed'] + self.metrics['commands_failed']
        if total == 0:
            return 100.0
        return (self.metrics['commands_executed'] / total) * 100
        
    def _get_top_commands(self) -> Dict[str, int]:
        """Получить топ-5 команд"""
        sorted_commands = sorted(
            self.metrics['command_types'].items(),
            key=lambda x: x[1],
            reverse=True
        )
        return dict(sorted_commands[:5])
        
    def reset_metrics(self):
        """Сброс метрик"""
        self.metrics = {
            'commands_executed': 0,
            'commands_failed': 0,
            'security_blocks': 0,
            'uptime_start': time.time(),
            'last_activity': None,
            'user_activity': {},
            'command_types': {},
            'errors': []
        }
        self.save_metrics()
        bot_logger.info("Метрики сброшены")

# Глобальный экземпляр метрик
metrics = MetricsCollector()