import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime
from config import Config

class BotLogger:
    def __init__(self):
        self.setup_logging()
        
    def setup_logging(self):
        """Настройка системы логирования"""
        # Создаем директорию для логов
        os.makedirs(os.path.dirname(Config.BOT_LOG_FILE), exist_ok=True)
        
        # Настройка основного логгера
        self.logger = logging.getLogger('telegram_bot')
        self.logger.setLevel(getattr(logging, Config.LOG_LEVEL))
        
        # Ротация логов
        file_handler = RotatingFileHandler(
            Config.BOT_LOG_FILE,
            maxBytes=Config.MAX_LOG_SIZE,
            backupCount=5,
            encoding='utf-8'
        )
        
        # Консольный вывод
        console_handler = logging.StreamHandler()
        
        # Формат логов
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Логгер для команд
        self.command_logger = logging.getLogger('commands')
        self.command_logger.setLevel(logging.INFO)
        
        command_handler = RotatingFileHandler(
            'logs/commands.log',
            maxBytes=Config.MAX_LOG_SIZE,
            backupCount=10,
            encoding='utf-8'
        )
        
        command_formatter = logging.Formatter(
            '%(asctime)s - User:%(user_id)s - Command:%(command)s - Status:%(status)s'
        )
        command_handler.setFormatter(command_formatter)
        self.command_logger.addHandler(command_handler)
        
    def info(self, message: str):
        """Информационное сообщение"""
        self.logger.info(message)
        
    def warning(self, message: str):
        """Предупреждение"""
        self.logger.warning(message)
        
    def error(self, message: str, exc_info=None):
        """Ошибка"""
        self.logger.error(message, exc_info=exc_info)
        
    def debug(self, message: str):
        """Отладочное сообщение"""
        self.logger.debug(message)
        
    def log_command(self, user_id: int, command: str, status: str, error: str = None):
        """Логирование команды"""
        extra = {
            'user_id': user_id,
            'command': command,
            'status': status
        }
        
        message = f"Command execution"
        if error:
            message += f" - Error: {error}"
            
        self.command_logger.info(message, extra=extra)
        
    def log_security_event(self, user_id: int, event_type: str, details: str):
        """Логирование событий безопасности"""
        self.logger.warning(
            f"SECURITY EVENT - User:{user_id} - Type:{event_type} - Details:{details}"
        )
        
    def log_system_event(self, event_type: str, details: str):
        """Логирование системных событий"""
        self.logger.info(f"SYSTEM EVENT - Type:{event_type} - Details:{details}")

# Глобальный экземпляр логгера
bot_logger = BotLogger()