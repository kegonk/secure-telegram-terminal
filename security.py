import re
import asyncio
import signal
from typing import Tuple, Optional
from config import Config

class SecurityManager:
    def __init__(self):
        self.pending_confirmations = {}
        
    def validate_command(self, command: str) -> Tuple[bool, str]:
        """Валидация команды на безопасность"""
        if not command or len(command.strip()) == 0:
            return False, "Пустая команда"
            
        if len(command) > Config.MAX_COMMAND_LENGTH:
            return False, f"Команда слишком длинная (>{Config.MAX_COMMAND_LENGTH} символов)"
            
        # Проверка на опасные команды
        command_lower = command.lower()
        for dangerous in Config.DANGEROUS_COMMANDS:
            if dangerous in command_lower:
                return False, f"Опасная команда заблокирована: {dangerous}"
        
        # Проверка на системные команды
        for system_cmd in Config.SYSTEM_COMMANDS:
            if command_lower.startswith(system_cmd):
                return False, f"Системная команда требует подтверждения: {system_cmd}"
                
        # Проверка на подозрительные паттерны
        suspicious_patterns = [
            r'>\s*/dev/null\s*2>&1\s*&',  # Скрытие вывода и фоновый запуск
            r'nohup\s+.*\s*&',            # Запуск в фоне
            r'while\s+true\s*;',          # Бесконечные циклы
            r'fork\(\)',                  # Форк бомбы
            r':\(\)\{.*\}\s*;',          # Bash fork bomb
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"Подозрительный паттерн в команде"
                
        return True, "OK"
        
    def is_system_command(self, command: str) -> bool:
        """Проверка является ли команда системной"""
        command_lower = command.lower()
        return any(command_lower.startswith(cmd) for cmd in Config.SYSTEM_COMMANDS)
        
    def requires_confirmation(self, command: str, user_id: int) -> bool:
        """Проверка нужно ли подтверждение для команды"""
        if self.is_system_command(command):
            return user_id not in self.pending_confirmations or \
                   self.pending_confirmations[user_id] != command
        return False
        
    def add_pending_confirmation(self, user_id: int, command: str):
        """Добавить команду в ожидание подтверждения"""
        self.pending_confirmations[user_id] = command
        
    def confirm_command(self, user_id: int, command: str) -> bool:
        """Подтвердить выполнение команды"""
        if user_id in self.pending_confirmations and \
           self.pending_confirmations[user_id] == command:
            del self.pending_confirmations[user_id]
            return True
        return False

class CommandExecutor:
    def __init__(self):
        self.running_processes = {}
        
    async def execute_with_timeout(self, command: list, timeout: int = Config.COMMAND_TIMEOUT) -> Tuple[bool, str]:
        """Выполнение команды с таймаутом"""
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=timeout
                )
                
                if process.returncode == 0:
                    return True, "Команда выполнена успешно"
                else:
                    error_msg = stderr.decode() if stderr else "Неизвестная ошибка"
                    return False, f"Ошибка выполнения: {error_msg}"
                    
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return False, f"Команда превысила таймаут ({timeout}s)"
                
        except Exception as e:
            return False, f"Ошибка запуска команды: {str(e)}"
            
    def kill_process(self, session_name: str) -> bool:
        """Убить процесс в tmux сессии"""
        try:
            # Отправляем Ctrl+C в сессию
            import subprocess
            subprocess.run(["tmux", "send-keys", "-t", session_name, "C-c"], 
                         timeout=5, check=True)
            return True
        except Exception:
            return False