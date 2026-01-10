#!/usr/bin/env python3
"""
Модуль для отправки уведомлений о статусе бота
"""

import asyncio
import httpx
from datetime import datetime
from config import Config
from logger import bot_logger

class BotNotifications:
    def __init__(self):
        self.bot_token = Config.BOT_TOKEN
        self.chat_id = Config.ALLOWED_CHAT_ID
        
    async def send_notification(self, message: str, parse_mode: str = "Markdown"):
        """Отправка уведомления в Telegram"""
        if not self.bot_token or not self.chat_id:
            bot_logger.warning("Не настроены BOT_TOKEN или ALLOWED_CHAT_ID для уведомлений")
            return False
            
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=data)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("ok"):
                        bot_logger.info("Уведомление отправлено успешно")
                        return True
                    else:
                        bot_logger.error(f"Ошибка Telegram API: {result}")
                        return False
                else:
                    bot_logger.error(f"HTTP ошибка при отправке уведомления: {response.status_code}")
                    return False
                    
        except Exception as e:
            bot_logger.error(f"Ошибка отправки уведомления: {e}")
            return False
    
    async def send_startup_notification(self):
        """Уведомление о запуске бота"""
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        message = f"""
🤖 *Telegram Terminal Bot запущен!*

⏰ Время запуска: `{current_time}`
✅ Статус: Готов к работе
🔧 Версия: Улучшенная с постоянными кнопками

📱 *Доступные команды:*
• Отправьте `/start` для получения кнопок
• Используйте постоянные кнопки для управления
• `/screenshot` - текущее состояние терминала

🎯 *Быстрые кнопки активны:*
↩️ Enter | ⬇️ Down | ⬅️ Left | ➡️ Right

---
*Бот готов к управлению терминалом!* 🚀
        """
        
        return await self.send_notification(message)
    
    async def send_shutdown_notification(self):
        """Уведомление об остановке бота"""
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        message = f"""
🛑 *Telegram Terminal Bot остановлен*

⏰ Время остановки: `{current_time}`
⚠️ Статус: Недоступен
🔧 Причина: Плановая остановка или перезагрузка

📋 *Для восстановления работы:*
• Проверьте статус Docker контейнера
• Перезапустите при необходимости
• Бот автоматически перезапустится при сбое

---
*Бот временно недоступен* ⏸️
        """
        
        return await self.send_notification(message)
    
    async def send_error_notification(self, error_message: str):
        """Уведомление об ошибке"""
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        message = f"""
❌ *Ошибка в Telegram Terminal Bot*

⏰ Время: `{current_time}`
🔴 Ошибка: `{error_message}`

🔧 *Рекомендуемые действия:*
• Проверьте логи: `docker compose logs`
• Перезапустите бота: `docker compose restart`
• Проверьте статус tmux сессии

---
*Требуется внимание администратора* ⚠️
        """
        
        return await self.send_notification(message)
    
    async def send_status_notification(self, status_info: dict):
        """Уведомление со статистикой работы"""
        current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        message = f"""
📊 *Статус Telegram Terminal Bot*

⏰ Время: `{current_time}`
✅ Статус: {status_info.get('status', 'Неизвестен')}
⏱️ Время работы: {status_info.get('uptime', 'N/A')}

📈 *Статистика:*
• Команд выполнено: {status_info.get('commands_executed', 0)}
• Команд с ошибками: {status_info.get('commands_failed', 0)}
• Успешность: {status_info.get('success_rate', 0):.1f}%

🔧 *Система:*
• tmux сессия: {status_info.get('tmux_status', 'Неизвестно')}
• Docker: {status_info.get('docker_status', 'Неизвестно')}

---
*Автоматический отчет о работе* 📋
        """
        
        return await self.send_notification(message)

# Создаем глобальный экземпляр для использования
notifications = BotNotifications()

async def send_startup_notification():
    """Функция для отправки уведомления о запуске"""
    return await notifications.send_startup_notification()

async def send_shutdown_notification():
    """Функция для отправки уведомления об остановке"""
    return await notifications.send_shutdown_notification()

async def send_error_notification(error: str):
    """Функция для отправки уведомления об ошибке"""
    return await notifications.send_error_notification(error)

# Синхронные версии для использования в signal handlers
def send_startup_notification_sync():
    """Синхронная версия уведомления о запуске"""
    try:
        asyncio.run(send_startup_notification())
    except Exception as e:
        bot_logger.error(f"Ошибка отправки уведомления о запуске: {e}")

def send_shutdown_notification_sync():
    """Синхронная версия уведомления об остановке"""
    try:
        asyncio.run(send_shutdown_notification())
    except Exception as e:
        bot_logger.error(f"Ошибка отправки уведомления об остановке: {e}")