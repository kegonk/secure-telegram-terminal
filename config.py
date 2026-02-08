import os
from typing import Set
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Основные настройки
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ALLOWED_CHAT_ID = int(os.getenv("ALLOWED_CHAT_ID", "0"))
    
    # Tmux настройки
    TMUX_SESSION = os.getenv("TMUX_SESSION", "claude")
    COMMAND_TIMEOUT = int(os.getenv("COMMAND_TIMEOUT", "30"))

    # Сетевые таймауты Telegram API (сек)
    TELEGRAM_CONNECT_TIMEOUT = float(os.getenv("TELEGRAM_CONNECT_TIMEOUT", "20"))
    TELEGRAM_READ_TIMEOUT = float(os.getenv("TELEGRAM_READ_TIMEOUT", "30"))
    TELEGRAM_WRITE_TIMEOUT = float(os.getenv("TELEGRAM_WRITE_TIMEOUT", "30"))
    TELEGRAM_POOL_TIMEOUT = float(os.getenv("TELEGRAM_POOL_TIMEOUT", "10"))

    # Повторные попытки запуска при сетевых ошибках
    RETRY_MAX = int(os.getenv("RETRY_MAX", "10"))  # 0 или меньше = бесконечно
    RETRY_BASE_DELAY = int(os.getenv("RETRY_BASE_DELAY", "5"))
    RETRY_MAX_DELAY = int(os.getenv("RETRY_MAX_DELAY", "60"))
    
    # Логирование
    LOG_FILE = os.getenv("LOG_FILE", f"logs/{os.getenv('TMUX_SESSION', 'claude')}_terminal.log")
    BOT_LOG_FILE = os.getenv("BOT_LOG_FILE", "logs/bot.log")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    MAX_LOG_SIZE = int(os.getenv("MAX_LOG_SIZE", "10485760"))  # 10MB
    
    # Безопасность
    SPAM_PROTECTION_SECONDS = int(os.getenv("SPAM_PROTECTION_SECONDS", "5"))
    MAX_COMMAND_LENGTH = int(os.getenv("MAX_COMMAND_LENGTH", "500"))
    
    # Опасные команды для блокировки
    DANGEROUS_COMMANDS: Set[str] = {
        "rm -rf", "sudo rm", "chmod 777", "mkfs", "dd if=", 
        ":(){ :|:& };:", "sudo chmod", "sudo chown", "format",
        "fdisk", "cfdisk", "parted", "wipefs", "shred",
        "wget ", "curl ", "| bash", "| sh", "> /dev/", 
        "echo > ", "cat > /", "nc -", "netcat", ">/dev/tcp",
        "> /etc/", "> /usr/", "> /bin/", "> /sbin/", "> /var/log/"
    }
    
    # Системные команды требующие подтверждения
    SYSTEM_COMMANDS: Set[str] = {
        "sudo", "su", "passwd", "usermod", "userdel", "groupdel",
        "systemctl", "service", "reboot", "shutdown", "halt"
    }
    
    # Метрики
    METRICS_ENABLED = os.getenv("METRICS_ENABLED", "true").lower() == "true"
    METRICS_FILE = os.getenv("METRICS_FILE", "logs/metrics.json")
    
    # Telegram настройки
    MESSAGE_MAX_LENGTH = 4096
    TAIL_LINES = int(os.getenv("TAIL_LINES", "50"))
    
    @classmethod
    def validate(cls) -> bool:
        """Валидация конфигурации"""
        if not cls.BOT_TOKEN:
            print("❌ BOT_TOKEN не найден в .env")
            return False
        if not cls.ALLOWED_CHAT_ID:
            print("❌ ALLOWED_CHAT_ID не найден в .env")
            return False
        return True

# Специальные клавиши для tmux
SPECIAL_KEYS = {
    "Enter": "C-m",
    "Ctrl+C": "C-c", 
    "Tab": "Tab",
    "Shift+Tab": "\033[Z",
    "Up": "Up",
    "Down": "Down", 
    "Left": "Left",
    "Right": "Right",
    "Ctrl+Z": "C-z",
    "Ctrl+D": "C-d",
    "Escape": "Escape"
}
