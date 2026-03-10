#!/usr/bin/env python3
"""
Telegram Terminal Bot - Improved Version
Полностью переработанная версия с правильной архитектурой и интеграцией всех модулей
"""

import asyncio
import httpx
import os
import subprocess
import signal
import sys
from typing import Optional, List
from datetime import datetime

from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TimedOut, NetworkError
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    ContextTypes, filters, CallbackQueryHandler
)
from telegram.request import HTTPXRequest

# Импорт наших модулей
from config import Config, SPECIAL_KEYS
from security import SecurityManager, CommandExecutor
from logger import bot_logger
from metrics import metrics
from history import command_history
from notifications import notifications
from text_utils import format_for_telegram


class IPv4HTTPXRequest(HTTPXRequest):
    """HTTPXRequest c принудительным IPv4 (обход проблем с IPv6)."""

    def _build_client(self) -> httpx.AsyncClient:
        transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
        return httpx.AsyncClient(**self._client_kwargs, transport=transport)  # type: ignore[arg-type]

class TelegramTerminalBot:
    """Главный класс бота с полной интеграцией всех модулей"""
    
    def __init__(self):
        """Инициализация бота и всех подсистем"""
        # Загрузка конфигурации
        load_dotenv()
        if not Config.validate():
            raise ValueError("Неверная конфигурация. Проверьте .env файл")
            
        # Инициализация компонентов
        self.security_manager = SecurityManager()
        self.command_executor = CommandExecutor()
        
        # Глобальные переменные для антиспама
        self.last_sent_command = ""
        self.last_sent_time = 0
        
        bot_logger.info("Бот инициализирован")
        
    def get_tmux_env(self) -> dict:
        """Получение окружения для tmux команд"""
        env = os.environ.copy()
        return env
    
    def create_reply_keyboard(self) -> ReplyKeyboardMarkup:
        """Создание постоянной клавиатуры с быстрыми командами"""
        keyboard = [
            ["📄 /tail", "🔍 /screenshot", "📊 /stats"],
            ["↩️ Enter", "⬇️ Down", "⬅️ Left", "➡️ Right"],
            ["🔄 /status", "📜 /history", "⚡ /buttons"],
            ["🧭 /session", "🩺 /health"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    def create_inline_keyboard(self) -> InlineKeyboardMarkup:
        """Создание inline клавиатуры с дополнительными функциями"""
        keyboard = [
            [InlineKeyboardButton("🔧 Команды", callback_data="show_commands")],
            [InlineKeyboardButton("📊 Статистика", callback_data="show_stats")],
            [InlineKeyboardButton("🛡️ Безопасность", callback_data="show_security")],
            [InlineKeyboardButton("❌ Убить процесс", callback_data="kill_process")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def is_allowed(self, update: Update) -> bool:
        """Проверка доступа пользователя"""
        return update.effective_chat.id == Config.ALLOWED_CHAT_ID

    async def _reply(
        self,
        update: Update,
        text: str,
        parse_mode: Optional[str] = None,
        reply_markup=None
    ):
        """Безопасный ответ для message/callback_query."""
        if update.message:
            await update.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
            return
        if update.callback_query and update.callback_query.message:
            await update.callback_query.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
            return

    async def _run_subprocess(
        self,
        cmd: List[str],
        timeout: int,
        env: Optional[dict] = None,
        capture_output: bool = True,
        text: bool = True
    ) -> subprocess.CompletedProcess:
        """Запуск subprocess без блокировки event loop."""
        return await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=capture_output,
            text=text,
            env=env,
            timeout=timeout
        )

    def _get_tmux_sessions_sync(self) -> List[str]:
        """Список tmux сессий (синхронно)."""
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
            env=self.get_tmux_env()
        )
        if result.returncode != 0:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    async def _get_tmux_sessions(self) -> List[str]:
        """Список tmux сессий (асинхронно)."""
        return await asyncio.to_thread(self._get_tmux_sessions_sync)

    async def _check_telegram_api(self) -> str:
        """Проверка доступности Telegram API."""
        if not Config.BOT_TOKEN:
            return "❌ BOT_TOKEN не задан"
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/getMe"
        timeout = httpx.Timeout(
            connect=Config.TELEGRAM_CONNECT_TIMEOUT,
            read=Config.TELEGRAM_READ_TIMEOUT,
            write=Config.TELEGRAM_WRITE_TIMEOUT,
            pool=Config.TELEGRAM_POOL_TIMEOUT
        )
        transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
                resp = await client.get(url)
            if resp.status_code == 200:
                return "✅ OK"
            return f"⚠️ HTTP {resp.status_code}"
        except Exception as e:
            return f"❌ {type(e).__name__}"

    def _update_env_tmux_session(self, name: str):
        """Обновить TMUX_SESSION (и LOG_FILE, если он стандартный) в .env."""
        env_path = os.path.join(os.getcwd(), ".env")
        if not os.path.exists(env_path):
            return

        lines = []
        found = False
        log_found = False
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("TMUX_SESSION="):
                    lines.append(f"TMUX_SESSION={name}\n")
                    found = True
                elif line.startswith("LOG_FILE="):
                    log_found = True
                    # Обновляем только если это стандартный формат логов
                    if line.strip().startswith("LOG_FILE=logs/") and line.strip().endswith("_terminal.log"):
                        lines.append(f"LOG_FILE=logs/{name}_terminal.log\n")
                    else:
                        lines.append(line)
                else:
                    lines.append(line)
        if not found:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] = lines[-1] + "\n"
            lines.append(f"TMUX_SESSION={name}\n")
        if not log_found:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] = lines[-1] + "\n"
            lines.append(f"LOG_FILE=logs/{name}_terminal.log\n")

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

    def _update_state_tmux_session(self, name: str):
        """Сохранить активную сессию в data/state.json."""
        os.makedirs("data", exist_ok=True)
        state_path = os.path.join("data", "state.json")
        state = {"tmux_session": name, "updated_at": datetime.utcnow().isoformat()}
        with open(state_path, "w", encoding="utf-8") as f:
            import json
            json.dump(state, f, ensure_ascii=False, indent=2)

    def _read_state_tmux_session(self) -> Optional[str]:
        """Прочитать активную сессию из data/state.json."""
        state_path = os.path.join("data", "state.json")
        if not os.path.exists(state_path):
            return None
        try:
            import json
            with open(state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                value = data.get("tmux_session")
                return value if isinstance(value, str) and value.strip() else None
        except Exception:
            return None
        return None

    async def _ensure_tmux_session(self) -> Optional[str]:
        """Убедиться, что активная tmux-сессия существует. Если нет — создать."""
        sessions = await self._get_tmux_sessions()

        # Если текущая сессия существует — ок
        if Config.TMUX_SESSION in sessions:
            return Config.TMUX_SESSION

        # Попробуем восстановить из state.json
        state_name = self._read_state_tmux_session()
        if state_name and state_name in sessions:
            self._set_active_session(state_name, update_env=False, update_state=False)
            return state_name

        # Если заданная сессия отсутствует, пытаемся создать
        target = Config.TMUX_SESSION or "default"
        result = await self._run_subprocess(
            ["tmux", "new-session", "-d", "-s", target, "-c", os.getcwd()],
            timeout=10,
            env=self.get_tmux_env()
        )
        if result.returncode == 0:
            self._set_active_session(target, update_env=True, update_state=True)
            return target

        # Если создать не удалось, но есть другие сессии — переключаемся на первую
        if sessions:
            self._set_active_session(sessions[0], update_env=True, update_state=True)
            return sessions[0]
        return None
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        if not self.is_allowed(update):
            await update.message.reply_text("❌ Доступ запрещен.")
            bot_logger.log_security_event(
                update.effective_chat.id, 
                "UNAUTHORIZED_ACCESS", 
                "/start command"
            )
            return
        
        bot_logger.info(f"Получена команда /start от пользователя {update.effective_chat.id} в чате {update.effective_chat.id}")
        
        reply_keyboard = self.create_reply_keyboard()
        inline_keyboard = self.create_inline_keyboard()
        
        welcome_msg = f"""🤖 **Telegram Terminal Bot запущен!**

✅ **Подключение к терминалу активно**
🖥️ **Сессия tmux:** `{Config.TMUX_SESSION}`
🛡️ **Безопасность:** Включена

⚡ **Быстрые команды доступны на кнопках ниже:**
• Используйте кнопки для управления терминалом
• Отправляйте команды напрямую в чат
• `/send <команда>` для отправки команд в терминал
• `/session current` чтобы узнать активную сессию

🎯 **Готов к работе!**"""

        bot_logger.info(f"Отправка сообщения с кнопками пользователю {update.effective_chat.id}")
        
        try:
            await update.message.reply_text(
                welcome_msg,
                parse_mode="Markdown",
                reply_markup=reply_keyboard
            )
            
            # Отправляем также inline кнопки
            await update.message.reply_text(
                "🔧 **Дополнительные функции:**",
                parse_mode="Markdown",
                reply_markup=inline_keyboard
            )
            
            bot_logger.info(f"Сообщение с кнопками успешно отправлено пользователю {update.effective_chat.id}")
            
        except Exception as e:
            bot_logger.error(f"Ошибка отправки сообщения: {e}")
            await update.message.reply_text("❌ Ошибка отправки сообщения с кнопками")
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик inline кнопок"""
        if not self.is_allowed(update):
            await update.callback_query.answer("❌ Доступ запрещен")
            return
        
        query = update.callback_query
        await query.answer()
        
        if query.data == "show_commands":
            await self.show_available_commands(update, context)
        elif query.data == "show_stats":
            await self.get_stats(update, context)
        elif query.data == "show_security":
            await self.show_security_info(update, context)
        elif query.data == "kill_process":
            await self.kill_current_process(update, context)
    
    async def send_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отправка команды в терминал с полной проверкой безопасности"""
        if not self.is_allowed(update):
            await update.message.reply_text("❌ Доступ запрещен.")
            return
        
        if not context.args:
            await update.message.reply_text("⚠️ Использование: /send <команда>")
            return
        
        command = " ".join(context.args).strip()
        user_id = update.effective_chat.id
        await self._process_command(update, command, user_id)

    async def _process_command(self, update: Update, command: str, user_id: int):
        """Общая логика обработки команды с проверками."""
        # Антиспам защита
        import time
        current_time = time.time()
        if (command == self.last_sent_command and
            current_time - self.last_sent_time < Config.SPAM_PROTECTION_SECONDS):
            return

        self.last_sent_command = command
        self.last_sent_time = current_time

        # Проверка безопасности
        is_valid, error_msg = self.security_manager.validate_command(command)
        if not is_valid:
            await self._reply(update, f"🛡️ Команда заблокирована: {error_msg}")
            metrics.increment_security_block(user_id, command, error_msg)
            bot_logger.log_security_event(user_id, "COMMAND_BLOCKED", f"{command} - {error_msg}")
            return

        # Проверка системных команд
        if self.security_manager.requires_confirmation(command, user_id):
            await self._reply(
                update,
                f"⚠️ Системная команда требует подтверждения: `{command}`\n"
                f"Отправьте `/confirm {command}` для выполнения",
                parse_mode="Markdown"
            )
            self.security_manager.add_pending_confirmation(user_id, command)
            return

        # Выполнение команды
        await self._execute_command(update, command, user_id)
    
    async def confirm_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение выполнения системной команды"""
        if not self.is_allowed(update):
            await update.message.reply_text("❌ Доступ запрещен.")
            return
        
        if not context.args:
            await update.message.reply_text("⚠️ Использование: /confirm <команда>")
            return
        
        command = " ".join(context.args).strip()
        user_id = update.effective_chat.id
        
        if self.security_manager.confirm_command(user_id, command):
            await update.message.reply_text(f"✅ Системная команда подтверждена: `{command}`", parse_mode="Markdown")
            await self._execute_command(update, command, user_id)
        else:
            await update.message.reply_text("❌ Команда не найдена в ожидающих подтверждения")
    
    async def _execute_command(self, update: Update, command: str, user_id: int):
        """Внутренний метод выполнения команды"""
        try:
            await self._ensure_tmux_session()
            # Проверяем специальные команды
            if command in SPECIAL_KEYS:
                # Отправляем специальную клавишу
                cmd = ["tmux", "send-keys", "-t", Config.TMUX_SESSION, SPECIAL_KEYS[command]]
            else:
                # Отправляем обычный текст
                cmd = ["tmux", "send-keys", "-t", Config.TMUX_SESSION, command]

            result = await self._run_subprocess(
                cmd,
                timeout=Config.COMMAND_TIMEOUT,
                env=self.get_tmux_env()
            )

            # Если это не специальная клавиша, отправляем Enter
            if command not in SPECIAL_KEYS and result.returncode == 0:
                await self._run_subprocess(
                    ["tmux", "send-keys", "-t", Config.TMUX_SESSION, "C-m"],
                    timeout=Config.COMMAND_TIMEOUT,
                    env=self.get_tmux_env()
                )
            
            if result.returncode == 0:
                await self._reply(update, f"✅ Команда выполнена: `{command}`", parse_mode="Markdown")
                
                # Логирование и метрики
                command_history.add_command(user_id, command, True)
                metrics.increment_command_executed(user_id, command)
                bot_logger.log_command(user_id, command, "SUCCESS")
                
            else:
                error_msg = result.stderr or "Неизвестная ошибка"
                await self._reply(update, f"❌ Ошибка выполнения: {error_msg}")
                
                # Логирование ошибки
                command_history.add_command(user_id, command, False)
                metrics.increment_command_failed(user_id, command, error_msg)
                bot_logger.log_command(user_id, command, "ERROR", error_msg)
        
        except subprocess.TimeoutExpired:
            await self._reply(update, f"⏰ Команда превысила таймаут ({Config.COMMAND_TIMEOUT}s)")
            metrics.increment_command_failed(user_id, command, "TIMEOUT")
            
        except Exception as e:
            await self._reply(update, f"❌ Ошибка: {str(e)}")
            metrics.increment_command_failed(user_id, command, str(e))
            bot_logger.error(f"Ошибка выполнения команды {command}: {e}")
    
    async def get_tail(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение последних строк из логов терминала"""
        if not self.is_allowed(update):
            await update.message.reply_text("❌ Доступ запрещен.")
            return

        await self._ensure_tmux_session()

        lines = Config.TAIL_LINES
        if context.args:
            try:
                lines = int(context.args[0])
                lines = max(1, min(lines, 100))
            except ValueError:
                pass
        
        try:
            if os.path.exists(Config.LOG_FILE):
                try:
                    file_size = os.path.getsize(Config.LOG_FILE)
                    if file_size < 1024 * 1024:  # 1MB
                        with open(Config.LOG_FILE, 'r', encoding='utf-8') as f:
                            all_lines = f.readlines()
                            tail_lines = all_lines[-lines:]
                            content = ''.join(tail_lines).strip()
                    else:
                        with open(Config.LOG_FILE, 'rb') as f:
                            f.seek(0, 2)
                            file_size = f.tell()
                            buffer_size = min(4096, file_size)
                            f.seek(max(0, file_size - buffer_size))
                            buffer = f.read().decode('utf-8', errors='ignore')
                            all_lines = buffer.split('\n')
                            tail_lines = all_lines[-lines:]
                            content = '\n'.join(tail_lines).strip()
                
                except (IOError, OSError) as e:
                    content = f"Ошибка чтения файла: {e}"
                    tail_lines = []
                
                if content:
                    formatted_output = format_for_telegram(content)
                    lines_count = len(tail_lines) if tail_lines else 0
                    await update.message.reply_text(
                        f"📄 Последние {lines_count} строк из логов терминала:\n\n{formatted_output}"
                    )
                else:
                    await update.message.reply_text("📄 Лог файл пуст")
            else:
                # Fallback к tmux
                await self._reply(update, f"⚠️ Файл логов `{Config.LOG_FILE}` не найден. Показываю содержимое tmux:")
                
                cmd = ["tmux", "capture-pane", "-t", Config.TMUX_SESSION, "-p"]
                result = await self._run_subprocess(
                    cmd,
                    timeout=10,
                    env=self.get_tmux_env()
                )
                
                if result.returncode == 0:
                    output = result.stdout.strip()
                    if output:
                        lines_list = output.split('\n')
                        tail_lines = lines_list[-lines:]
                        formatted_output = format_for_telegram('\n'.join(tail_lines))
                        await self._reply(
                            update,
                            f"📄 Последние {len(tail_lines)} строк из tmux:\n\n{formatted_output}"
                        )
                    else:
                        await self._reply(update, "📄 Терминал пуст")
        
        except Exception as e:
            await self._reply(update, f"❌ Ошибка чтения логов: {str(e)}")
            bot_logger.error(f"Ошибка в get_tail: {e}")
    
    async def get_screenshot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение текущего состояния терминала"""
        if not self.is_allowed(update):
            await update.message.reply_text("❌ Доступ запрещен.")
            return

        await self._ensure_tmux_session()
        
        try:
            cmd = ["tmux", "capture-pane", "-t", Config.TMUX_SESSION, "-p"]
            result = await self._run_subprocess(
                cmd,
                timeout=10,
                env=self.get_tmux_env()
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if output:
                    lines_list = output.split('\n')
                    if len(lines_list) > 50:
                        lines_list = lines_list[-50:]
                        prefix = "🔍 Скриншот терминала (последние 50 строк):\n\n"
                    else:
                        prefix = "🔍 Полный скриншот терминала:\n\n"
                    
                    formatted_output = format_for_telegram('\n'.join(lines_list))
                    await self._reply(update, f"{prefix}{formatted_output}")
                else:
                    await self._reply(update, "🔍 Терминал пуст или сессия недоступна")
            else:
                await self._reply(update, f"❌ Ошибка получения скриншота: {result.stderr}")
        
        except Exception as e:
            await self._reply(update, f"❌ Ошибка: {str(e)}")
            bot_logger.error(f"Ошибка в get_screenshot: {e}")
    
    async def get_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение статуса системы"""
        if not self.is_allowed(update):
            await update.message.reply_text("❌ Доступ запрещен.")
            return

        await self._ensure_tmux_session()
        
        try:
            # Проверяем tmux сессию
            tmux_check = await self._run_subprocess(
                ["tmux", "has-session", "-t", Config.TMUX_SESSION],
                timeout=10,
                env=self.get_tmux_env()
            )
            tmux_status = "✅ Активна" if tmux_check.returncode == 0 else "❌ Недоступна"
            
            # Получаем статистику
            stats = metrics.get_stats()
            
            status_msg = f"""🔄 **Статус системы:**

🖥️ **tmux сессия:** {tmux_status}
📂 **Сессия:** `{Config.TMUX_SESSION}`
🤖 **Бот:** ✅ Работает
⏱️ **Время работы:** {stats['uptime']}

📊 **Статистика:**
• Команд выполнено: {stats['commands_executed']}
• Команд с ошибками: {stats['commands_failed']}
• Блокировок безопасности: {stats['security_blocks']}
• Успешность: {stats['success_rate']:.1f}%

⚡ **Доступные команды:**
• `/send <команда>` - отправить команду
• `/tail [строки]` - последние строки
• `/screenshot` - текущее состояние
• `/status` - этот статус"""

            await self._reply(update, status_msg, parse_mode="Markdown")
        
        except Exception as e:
            await self._reply(update, f"❌ Ошибка получения статуса: {str(e)}")
            bot_logger.error(f"Ошибка в get_status: {e}")
    
    async def get_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение детальной статистики"""
        if not self.is_allowed(update):
            await update.message.reply_text("❌ Доступ запрещен.")
            return
        
        try:
            stats = metrics.get_stats()
            user_stats = command_history.get_user_stats(update.effective_chat.id)
            top_commands = metrics._get_top_commands()
            
            stats_msg = f"""📊 **Детальная статистика:**

⏱️ **Время работы:** {stats['uptime']}
👤 **Активных пользователей:** {stats['active_users']}

📈 **Команды:**
• Всего выполнено: {stats['commands_executed']}
• С ошибками: {stats['commands_failed']}
• Заблокировано: {stats['security_blocks']}
• Успешность: {stats['success_rate']:.1f}%

👤 **Ваша статистика:**
• Всего команд: {user_stats['total']}
• Успешных: {user_stats['success']}
• С ошибками: {user_stats['failed']}
• Ваша успешность: {user_stats['success_rate']:.1f}%

🔥 **Популярные команды:**"""

            for cmd, count in list(top_commands.items())[:5]:
                stats_msg += f"\n• `{cmd}`: {count} раз"
            
            await self._reply(update, stats_msg, parse_mode="Markdown")
        
        except Exception as e:
            await self._reply(update, f"❌ Ошибка получения статистики: {str(e)}")
            bot_logger.error(f"Ошибка в get_stats: {e}")
    
    async def show_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать историю команд"""
        if not self.is_allowed(update):
            await update.message.reply_text("❌ Доступ запрещен.")
            return
        
        try:
            user_id = update.effective_chat.id
            recent_commands = command_history.get_recent_commands(user_id, 10)
            
            if not recent_commands:
                await self._reply(update, "📜 История команд пуста")
                return
            
            history_msg = "📜 **Последние команды:**\n\n"
            for i, cmd in enumerate(recent_commands, 1):
                status = "✅" if cmd['success'] else "❌"
                timestamp = cmd['timestamp'][:19].replace('T', ' ')
                history_msg += f"{i}. {status} `{cmd['command']}` ({timestamp})\n"
            
            await self._reply(update, history_msg, parse_mode="Markdown")
        
        except Exception as e:
            await self._reply(update, f"❌ Ошибка получения истории: {str(e)}")
            bot_logger.error(f"Ошибка в show_history: {e}")
    
    async def search_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Поиск в истории команд"""
        if not self.is_allowed(update):
            await update.message.reply_text("❌ Доступ запрещен.")
            return
        
        if not context.args:
            await update.message.reply_text("⚠️ Использование: /search <запрос>")
            return
        
        try:
            query = " ".join(context.args)
            user_id = update.effective_chat.id
            results = command_history.search_history(query, user_id, 10)
            
            if not results:
                await self._reply(update, f"🔍 Команды с запросом '{query}' не найдены")
                return
            
            search_msg = f"🔍 **Найдено команд с '{query}':**\n\n"
            for i, cmd in enumerate(results, 1):
                status = "✅" if cmd['success'] else "❌"
                timestamp = cmd['timestamp'][:19].replace('T', ' ')
                search_msg += f"{i}. {status} `{cmd['command']}` ({timestamp})\n"
            
            await self._reply(update, search_msg, parse_mode="Markdown")
        
        except Exception as e:
            await self._reply(update, f"❌ Ошибка поиска: {str(e)}")
            bot_logger.error(f"Ошибка в search_history: {e}")

    async def session_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Управление tmux сессиями"""
        if not self.is_allowed(update):
            await self._reply(update, "❌ Доступ запрещен.")
            return

        await self._ensure_tmux_session()

        if not context.args:
            sessions = await self._get_tmux_sessions()
            if sessions:
                lines = []
                for name in sessions:
                    marker = " (current)" if name == Config.TMUX_SESSION else ""
                    lines.append(f"• `{name}`{marker}")
                msg = "🧭 **Tmux сессии:**\n\n" + "\n".join(lines)
            else:
                msg = "🧭 **Tmux сессии:**\n\n(нет активных сессий)"

            msg += (
                "\n\nИспользование:\n"
                "• `/session list`\n"
                "• `/session current`\n"
                "• `/session new <name>`\n"
                "• `/session switch <name>`\n"
                "• `/session kill <name>`\n"
                "• `/session rename <old> <new>`"
            )
            await self._reply(update, msg, parse_mode="Markdown")
            return

        action = context.args[0].lower()
        args = context.args[1:]

        if action == "list":
            sessions = await self._get_tmux_sessions()
            if not sessions:
                await self._reply(update, "🧭 Активных tmux сессий нет.")
                return
            lines = []
            for name in sessions:
                marker = " (current)" if name == Config.TMUX_SESSION else ""
                lines.append(f"• `{name}`{marker}")
            await self._reply(update, "🧭 **Tmux сессии:**\n\n" + "\n".join(lines), parse_mode="Markdown")
            return

        if action == "current":
            sessions = await self._get_tmux_sessions()
            if Config.TMUX_SESSION in sessions:
                await self._reply(update, f"🧭 Текущая сессия: `{Config.TMUX_SESSION}`", parse_mode="Markdown")
            else:
                await self._reply(update, "⚠️ Текущая сессия недоступна. Используйте `/session list`.", parse_mode="Markdown")
            return

        if action == "new":
            if len(args) < 1:
                await self._reply(update, "⚠️ Использование: `/session new <name>`", parse_mode="Markdown")
                return
            name = args[0].strip()
            sessions = await self._get_tmux_sessions()
            if name in sessions:
                await self._reply(update, f"⚠️ Сессия `{name}` уже существует.", parse_mode="Markdown")
                return
            result = await self._run_subprocess(
                ["tmux", "new-session", "-d", "-s", name, "-c", os.getcwd()],
                timeout=10,
                env=self.get_tmux_env()
            )
            if result.returncode == 0:
                self._set_active_session(name, update_env=True, update_state=True)
                await self._reply(update, f"✅ Сессия `{name}` создана и выбрана.", parse_mode="Markdown")
            else:
                await self._reply(update, f"❌ Ошибка создания сессии: {result.stderr}")
            return

        if action == "switch":
            if len(args) < 1:
                await self._reply(update, "⚠️ Использование: `/session switch <name>`", parse_mode="Markdown")
                return
            name = args[0].strip()
            sessions = await self._get_tmux_sessions()
            if name not in sessions:
                await self._reply(update, f"❌ Сессия `{name}` не найдена.", parse_mode="Markdown")
                return
            self._set_active_session(name, update_env=True, update_state=True)
            await self._reply(update, f"✅ Переключено на сессию `{name}`.", parse_mode="Markdown")
            return

        if action == "kill":
            if len(args) < 1:
                await self._reply(update, "⚠️ Использование: `/session kill <name>`", parse_mode="Markdown")
                return
            name = args[0].strip()
            result = await self._run_subprocess(
                ["tmux", "kill-session", "-t", name],
                timeout=10,
                env=self.get_tmux_env()
            )
            if result.returncode != 0:
                await self._reply(update, f"❌ Ошибка удаления сессии: {result.stderr}")
                return

            sessions = await self._get_tmux_sessions()
            if name == Config.TMUX_SESSION:
                if sessions:
                    self._set_active_session(sessions[0], update_env=True, update_state=True)
                    await self._reply(
                        update,
                        f"✅ Сессия `{name}` удалена. Переключено на `{Config.TMUX_SESSION}`.",
                        parse_mode="Markdown"
                    )
                else:
                    await self._reply(update, f"✅ Сессия `{name}` удалена. Активных сессий больше нет.", parse_mode="Markdown")
            else:
                await self._reply(update, f"✅ Сессия `{name}` удалена.", parse_mode="Markdown")
            return

        if action == "rename":
            if len(args) < 2:
                await self._reply(update, "⚠️ Использование: `/session rename <old> <new>`", parse_mode="Markdown")
                return
            old, new = args[0].strip(), args[1].strip()
            result = await self._run_subprocess(
                ["tmux", "rename-session", "-t", old, new],
                timeout=10,
                env=self.get_tmux_env()
            )
            if result.returncode != 0:
                await self._reply(update, f"❌ Ошибка переименования: {result.stderr}")
                return
            if Config.TMUX_SESSION == old:
                self._set_active_session(new, update_env=True, update_state=True)
            await self._reply(update, f"✅ Сессия `{old}` переименована в `{new}`.", parse_mode="Markdown")
            return

        await self._reply(update, "⚠️ Неизвестная команда. Используйте `/session list`.", parse_mode="Markdown")
    
    async def show_available_commands(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать доступные команды"""
        if not self.is_allowed(update):
            await self._reply(update, "❌ Доступ запрещен.")
            return
        
        commands_msg = """🔧 **Доступные команды:**

📤 **Основные:**
• `/send <команда>` - выполнить команду в терминале
• `/confirm <команда>` - подтвердить системную команду
• `/session <list|current|new|switch|kill|rename> ...` - управление tmux сессиями

📄 **Просмотр:**
• `/tail [строки]` - последние строки логов (по умолчанию 25)
• `/screenshot` - текущее состояние терминала
• `/status` - статус системы

📊 **Статистика:**
• `/stats` - детальная статистика
• `/history` - последние команды
• `/search <запрос>` - поиск в истории
• `/health` - диагностика бота

⚡ **Быстрые клавиши:**
• `Enter`, `Up`, `Down`, `Left`, `Right` - навигация
• `Ctrl+C` - прервать команду

🛡️ **Безопасность:**
• Все команды проверяются системой безопасности
• Опасные команды блокируются автоматически
• Системные команды требуют подтверждения"""

        await self._reply(update, commands_msg, parse_mode="Markdown")
    
    async def show_security_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать информацию о безопасности"""
        if not self.is_allowed(update):
            await self._reply(update, "❌ Доступ запрещен.")
            return
        
        security_msg = f"""🛡️ **Система безопасности:**

✅ **Активные защиты:**
• Контроль доступа по chat_id
• Валидация команд
• Обнаружение опасных паттернов
• Подтверждение системных команд
• Защита от спама ({Config.SPAM_PROTECTION_SECONDS}s)
• Таймаут команд ({Config.COMMAND_TIMEOUT}s)

🚫 **Заблокированные команды:**
• `rm -rf` - удаление файлов
• `sudo rm` - административное удаление
• `chmod 777` - опасные права
• `mkfs`, `dd if=` - форматирование дисков
• Fork bombs и подобные

⚠️ **Системные команды (требуют подтверждения):**
• `sudo`, `su` - административные права
• `systemctl`, `service` - управление сервисами
• `reboot`, `shutdown` - перезагрузка системы

📊 **Статистика безопасности:**
• Заблокировано команд: {metrics.get_stats()['security_blocks']}
• Все события логируются"""

        await self._reply(update, security_msg, parse_mode="Markdown")

    async def health(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Диагностика состояния бота"""
        if not self.is_allowed(update):
            await self._reply(update, "❌ Доступ запрещен.")
            return

        await self._ensure_tmux_session()

        sessions = await self._get_tmux_sessions()
        tmux_ok = "✅" if Config.TMUX_SESSION in sessions else "❌"

        log_exists = os.path.exists(Config.LOG_FILE)
        log_status = "✅" if log_exists else "❌"
        log_info = "нет"
        if log_exists:
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(Config.LOG_FILE)).strftime("%d.%m.%Y %H:%M:%S")
                size = os.path.getsize(Config.LOG_FILE)
                log_info = f"{mtime}, {size} bytes"
            except Exception:
                log_info = "не удалось прочитать"

        api_status = await self._check_telegram_api()
        stats = metrics.get_stats()

        msg = f"""🩺 **Health**

🤖 Бот: ✅
🖥️ tmux сессия: {tmux_ok} `{Config.TMUX_SESSION}`
🧭 Всего сессий: {len(sessions)}
📄 Логи: {log_status} `{Config.LOG_FILE}`
🕒 Логи: {log_info}
🌐 Telegram API: {api_status}
⏱️ Время работы: {stats['uptime']}
"""
        await self._reply(update, msg, parse_mode="Markdown")
    
    async def kill_current_process(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Убить текущий процесс в терминале"""
        if not self.is_allowed(update):
            await self._reply(update, "❌ Доступ запрещен.")
            return
        
        try:
            success = self.command_executor.kill_process(Config.TMUX_SESSION)
            if success:
                await self._reply(update, "✅ Сигнал Ctrl+C отправлен в терминал")
                metrics.increment_command_executed(update.effective_chat.id, "Ctrl+C")
            else:
                await self._reply(update, "❌ Ошибка отправки сигнала")
        
        except Exception as e:
            await self._reply(update, f"❌ Ошибка: {str(e)}")
            bot_logger.error(f"Ошибка в kill_current_process: {e}")
    
    async def handle_quick_buttons(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий на кнопки быстрого доступа"""
        if not self.is_allowed(update):
            await update.message.reply_text("❌ Доступ запрещен.")
            return
        
        message_text = update.message.text
        
        # Обработка кнопок управления
        if message_text == "↩️ Enter":
            await self._execute_command(update, "Enter", update.effective_chat.id)
        elif message_text == "⬇️ Down":
            await self._execute_command(update, "Down", update.effective_chat.id)
        elif message_text == "⬅️ Left":
            await self._execute_command(update, "Left", update.effective_chat.id)
        elif message_text == "➡️ Right":
            await self._execute_command(update, "Right", update.effective_chat.id)
        elif message_text == "📄 /tail":
            await self.get_tail(update, context)
        elif message_text == "🔍 /screenshot":
            await self.get_screenshot(update, context)
        elif message_text == "🔄 /status":
            await self.get_status(update, context)
        elif message_text == "📊 /stats":
            await self.get_stats(update, context)
        elif message_text == "📜 /history":
            await self.show_history(update, context)
        elif message_text == "⚡ /buttons":
            await self.show_available_commands(update, context)
        elif message_text == "🧭 /session":
            await self.session_command(update, context)
        elif message_text == "🩺 /health":
            await self.health(update, context)
        else:
            # Обрабатываем как обычную команду только если это не кнопка с эмодзи
            if not any(emoji in message_text for emoji in ["📄", "🔍", "📊", "↩️", "⬇️", "⬅️", "➡️", "🔄", "📜", "⚡", "🧭", "🩺"]):
                # Прямая отправка команды без /send (с проверками безопасности)
                await self._process_command(update, message_text, update.effective_chat.id)
            else:
                await update.message.reply_text(f"⚠️ Неизвестная команда: {message_text}")
    
    async def shutdown_handler(self, signum, frame):
        """Обработчик сигналов завершения"""
        bot_logger.info(f"Получен сигнал {signum}. Завершение работы...")
        
        shutdown_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        shutdown_message = f"""🛑 **Telegram Terminal Bot остановлен**

⏰ Время остановки: `{shutdown_time}`
⚠️ Статус: Недоступен
🔧 Причина: Получен сигнал завершения

Для перезапуска запустите бота вручную"""
        
        try:
            await notifications.send_shutdown_notification()
        except Exception as e:
            bot_logger.error(f"Ошибка отправки уведомления об остановке: {e}")
        
        bot_logger.info("Завершение работы бота...")
        sys.exit(0)

    async def post_init(self, application):
        """Настройка команд бота в Telegram UI."""
        commands = [
            ("start", "Запуск и клавиатуры"),
            ("send", "Отправить команду в терминал"),
            ("confirm", "Подтвердить системную команду"),
            ("session", "Управление tmux сессиями"),
            ("health", "Диагностика бота"),
            ("tail", "Последние строки логов"),
            ("screenshot", "Скриншот tmux"),
            ("status", "Статус системы"),
            ("stats", "Статистика"),
            ("history", "История команд"),
            ("search", "Поиск по истории"),
            ("buttons", "Список команд")
        ]
        try:
            await application.bot.set_my_commands(commands)
        except Exception as e:
            bot_logger.error(f"Ошибка установки команд бота: {e}")

        # Уведомление о старте только после успешной инициализации
        try:
            await notifications.send_startup_notification()
            bot_logger.info("Уведомление о запуске отправлено")
        except Exception as e:
            bot_logger.error(f"Ошибка отправки уведомления о запуске: {e}")
    
    def send_startup_notification(self):
        """Отправляем уведомление о запуске (синхронно)"""
        try:
            asyncio.run(notifications.send_startup_notification())
            bot_logger.info("Уведомление о запуске отправлено")
        except Exception as e:
            bot_logger.error(f"Ошибка отправки уведомления о запуске: {e}")
    
    def send_error_notification(self, error_msg):
        """Отправляем уведомление об ошибке (синхронно)"""
        try:
            asyncio.run(notifications.send_error_notification(error_msg))
            bot_logger.info("Уведомление об ошибке отправлено")
        except Exception as e:
            bot_logger.error(f"Ошибка отправки уведомления об ошибке: {e}")
    
    def signal_handler(self, signum, frame):
        """Обработчик сигналов"""
        bot_logger.info(f"Получен сигнал {signum}")
        sys.exit(0)
    
    def run(self):
        """Запуск бота"""
        retry_delay = Config.RETRY_BASE_DELAY
        attempts = 0
        while True:
            try:
                # Создаем приложение (принудительно IPv4, чтобы избежать таймаутов на IPv6)
                request = IPv4HTTPXRequest(
                    connect_timeout=Config.TELEGRAM_CONNECT_TIMEOUT,
                    read_timeout=Config.TELEGRAM_READ_TIMEOUT,
                    write_timeout=Config.TELEGRAM_WRITE_TIMEOUT,
                    pool_timeout=Config.TELEGRAM_POOL_TIMEOUT
                )
                app = ApplicationBuilder().token(Config.BOT_TOKEN).request(request).post_init(self.post_init).build()

                # Регистрируем обработчики команд
                app.add_handler(CommandHandler("start", self.start))
                app.add_handler(CommandHandler("send", self.send_command))
                app.add_handler(CommandHandler("confirm", self.confirm_command))
                app.add_handler(CommandHandler("tail", self.get_tail))
                app.add_handler(CommandHandler("screenshot", self.get_screenshot))
                app.add_handler(CommandHandler("status", self.get_status))
                app.add_handler(CommandHandler("stats", self.get_stats))
                app.add_handler(CommandHandler("history", self.show_history))
                app.add_handler(CommandHandler("search", self.search_history))
                app.add_handler(CommandHandler("buttons", self.show_available_commands))
                app.add_handler(CommandHandler("session", self.session_command))
                app.add_handler(CommandHandler("health", self.health))

                # Обработчик inline кнопок
                app.add_handler(CallbackQueryHandler(self.handle_callback_query))

                # Обработчик текстовых сообщений (для кнопок и прямых команд)
                app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_quick_buttons))

                # Регистрируем обработчики сигналов
                for sig in [signal.SIGINT, signal.SIGTERM]:
                    signal.signal(sig, self.signal_handler)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._ensure_tmux_session())
                bot_logger.info("🤖 Бот запущен и готов к работе")

                # Запускаем polling (блокирует до остановки)
                app.run_polling(drop_pending_updates=True)
                return

            except (TimedOut, NetworkError, httpx.ConnectTimeout) as e:
                attempts += 1
                bot_logger.error(f"Сетевой таймаут при запуске: {e}. Повтор через {retry_delay}s")
                import time
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, Config.RETRY_MAX_DELAY)
                if Config.RETRY_MAX > 0 and attempts >= Config.RETRY_MAX:
                    bot_logger.error("Превышен лимит повторов запуска. Остановка.")
                    raise
                continue

            except Exception as e:
                bot_logger.error(f"Критическая ошибка: {e}", exc_info=True)
                # Отправляем уведомление об ошибке
                import threading
                threading.Thread(target=self.send_error_notification, args=(str(e),)).start()

                error_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
                error_message = f"""❌ **Ошибка Telegram Terminal Bot**

⏰ Время: `{error_time}`
🔴 Ошибка: `{str(e)[:100]}...`
🔄 Перезапустите бота для продолжения работы"""

                # Уведомление об ошибке уже отправлено через Thread выше
                raise


def main():
    """Главная функция запуска бота"""
    print("🤖 Telegram Terminal Bot - Improved Version")
    print("🚀 Запуск бота...")
    
    try:
        # Создаем и запускаем бота
        bot = TelegramTerminalBot()
        
        # Запускаем синхронно (без asyncio.run)
        bot.run()
        
    except KeyboardInterrupt:
        print("\n🛑 Получен сигнал остановки...")
        
    except Exception as e:
        print(f"❌ Критическая ошибка при запуске: {e}")
        bot_logger.error(f"Критическая ошибка при запуске: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
    def _set_active_session(self, name: str, update_env: bool = True, update_state: bool = True):
        """Установить активную tmux-сессию и синхронизировать лог."""
        Config.TMUX_SESSION = name
        # Обновляем LOG_FILE только если он использует стандартный шаблон
        if Config.LOG_FILE.startswith("logs/") and Config.LOG_FILE.endswith("_terminal.log"):
            Config.LOG_FILE = f"logs/{name}_terminal.log"
        if update_env:
            self._update_env_tmux_session(name)
        if update_state:
            self._update_state_tmux_session(name)
