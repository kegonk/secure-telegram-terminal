import os
import subprocess
import time
import signal
import sys
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)
from text_utils import format_for_telegram

# Функция для создания окружения для локальной работы
def get_tmux_env():
    env = os.environ.copy()
    # Для локальной работы не устанавливаем специальный TMUX_TMPDIR
    # tmux будет использовать стандартный путь в /tmp
    return env

# Простая функция для отправки уведомлений
def send_simple_notification(message):
    """Отправка простого уведомления через curl без asyncio"""
    try:
        bot_token = BOT_TOKEN
        chat_id = ALLOWED_CHAT_ID
        
        import urllib.parse
        encoded_message = urllib.parse.quote(message)
        
        curl_cmd = [
            "curl", "-s", "-X", "POST",
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            "-d", f"chat_id={chat_id}",
            "-d", f"text={encoded_message}",
            "-d", "parse_mode=Markdown"
        ]
        
        subprocess.run(curl_cmd, capture_output=True, timeout=10)
        print(f"✅ Уведомление отправлено: {message[:50]}...")
    except Exception as e:
        print(f"❌ Ошибка отправки уведомления: {e}")

# --- Загрузка настроек из .env ---
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_CHAT_ID = int(os.getenv("ALLOWED_CHAT_ID", "0"))
TMUX_SESSION = os.getenv("TMUX_SESSION", "claude")
LOG_FILE = os.getenv("LOG_FILE", "logs/claude_terminal.log")

SPECIAL_KEYS = {
    "Enter": "C-m",
    "Ctrl+C": "C-c",
    "Tab": "Tab",
    "Shift+Tab": "\033[Z",
    "Up": "Up",
    "Down": "Down",
    "Left": "Left",
    "Right": "Right",
}

# --- Глобальные переменные для антиспама ---
last_sent_command = ""
last_sent_time = 0

# --- Создание постоянной клавиатуры ---
def create_reply_keyboard():
    """Создание постоянной клавиатуры с быстрыми кнопками"""
    keyboard = [
        ["📄 /tail", "🔍 /screenshot", "📊 /stats"],
        ["↩️ Enter", "⬇️ Down", "⬅️ Left", "➡️ Right"],
        ["🔄 /status", "📜 /history", "⚡ /buttons"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

# --- Проверка доступа ---
def is_allowed(update: Update) -> bool:
    return update.effective_chat.id == ALLOWED_CHAT_ID

# --- Отправка команд в tmux ---
async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_sent_command, last_sent_time
    if not is_allowed(update):
        await update.message.reply_text("❌ Access denied.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Использование: /send <текст или спецкоманда>")
        return

    arg = " ".join(context.args).strip()

    # Антиспам защита
    current_time = time.time()
    if arg == last_sent_command and current_time - last_sent_time < 2:
        return

    last_sent_command = arg
    last_sent_time = current_time

    try:
        # Проверяем специальные команды
        if arg in SPECIAL_KEYS:
            # Отправляем специальную клавишу
            cmd = ["tmux", "send-keys", "-t", TMUX_SESSION, SPECIAL_KEYS[arg]]
        else:
            # Отправляем обычный текст без Enter в конце
            cmd = ["tmux", "send-keys", "-t", TMUX_SESSION, arg]

        result = subprocess.run(cmd, capture_output=True, text=True, env=get_tmux_env(), timeout=10)
        
        if result.returncode == 0:
            await update.message.reply_text(f"✅ Команда отправлена: `{arg}`", parse_mode="Markdown")
        else:
            error_msg = result.stderr or "Неизвестная ошибка"
            await update.message.reply_text(f"❌ Ошибка выполнения: {error_msg}")

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

# --- Получение логов ---
async def get_tail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        await update.message.reply_text("❌ Access denied.")
        return

    lines = 20  # По умолчанию
    if context.args:
        try:
            lines = int(context.args[0])
            lines = max(1, min(lines, 100))  # От 1 до 100 строк
        except ValueError:
            pass

    try:
        # Читаем из файла логов (оптимизированное чтение для больших файлов)
        if os.path.exists(LOG_FILE):
            try:
                # Для небольших файлов (< 1MB) читаем полностью
                file_size = os.path.getsize(LOG_FILE)
                if file_size < 1024 * 1024:  # 1MB
                    with open(LOG_FILE, 'r', encoding='utf-8') as f:
                        all_lines = f.readlines()
                        tail_lines = all_lines[-lines:]
                        content = ''.join(tail_lines).strip()
                else:
                    # Для больших файлов используем более эффективный способ
                    with open(LOG_FILE, 'rb') as f:
                        # Читаем с конца файла
                        f.seek(0, 2)  # Идем в конец файла
                        file_size = f.tell()
                        
                        # Читаем последние ~4KB и парсим строки
                        buffer_size = min(4096, file_size)
                        f.seek(max(0, file_size - buffer_size))
                        buffer = f.read().decode('utf-8', errors='ignore')
                        
                        all_lines = buffer.split('\n')
                        tail_lines = all_lines[-lines:] if len(all_lines) >= lines else all_lines
                        content = '\n'.join(tail_lines).strip()
            except (IOError, OSError) as e:
                content = f"Ошибка чтения файла: {e}"
                tail_lines = []
                
            if content:
                formatted_output = format_for_telegram(content)
                lines_count = len(tail_lines) if 'tail_lines' in locals() else 0
                await update.message.reply_text(f"📄 Последние {lines_count} строк из логов терминала:\n\n{formatted_output}")
            else:
                await update.message.reply_text("📄 Лог файл пуст")
        else:
            # Если файл логов не существует, используем tmux как fallback
            await update.message.reply_text(f"⚠️ Файл логов `{LOG_FILE}` не найден. Показываю содержимое tmux:")
            
            cmd = ["tmux", "capture-pane", "-t", TMUX_SESSION, "-p"]
            result = subprocess.run(cmd, capture_output=True, text=True, env=get_tmux_env(), timeout=10)
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if output:
                    lines_list = output.split('\n')
                    tail_lines = lines_list[-lines:]
                    formatted_output = format_for_telegram('\n'.join(tail_lines))
                    await update.message.reply_text(f"📄 Последние {len(tail_lines)} строк из tmux:\n\n{formatted_output}")
                else:
                    await update.message.reply_text("📄 Терминал пуст")

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка чтения логов: {str(e)}")

# --- Получение скриншота терминала ---
async def get_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение текущего состояния терминала (скриншот)"""
    if not is_allowed(update):
        await update.message.reply_text("❌ Access denied.")
        return

    try:
        # Получаем полное содержимое tmux панели
        cmd = ["tmux", "capture-pane", "-t", TMUX_SESSION, "-p"]
        result = subprocess.run(cmd, capture_output=True, text=True, env=get_tmux_env(), timeout=10)
        
        if result.returncode == 0:
            output = result.stdout.strip()
            if output:
                # Для скриншота показываем все содержимое, но ограничиваем размер
                lines_list = output.split('\n')
                if len(lines_list) > 50:  # Ограничиваем до 50 строк для скриншота
                    lines_list = lines_list[-50:]
                    prefix = "🔍 Скриншот терминала (последние 50 строк):\n\n"
                else:
                    prefix = "🔍 Полный скриншот терминала:\n\n"
                
                formatted_output = format_for_telegram('\n'.join(lines_list))
                await update.message.reply_text(f"{prefix}{formatted_output}")
            else:
                await update.message.reply_text("🔍 Терминал пуст или сессия недоступна")
        else:
            await update.message.reply_text(f"❌ Ошибка получения скриншота: {result.stderr}")

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

# --- Статус системы ---
async def get_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        await update.message.reply_text("❌ Access denied.")
        return

    try:
        # Проверяем tmux сессию
        tmux_check = subprocess.run(
            ["tmux", "has-session", "-t", TMUX_SESSION], 
            capture_output=True,
            env=get_tmux_env()
        )
        tmux_status = "✅ Активна" if tmux_check.returncode == 0 else "❌ Недоступна"

        status_msg = f"""🔄 **Статус системы:**

🖥️ **tmux сессия:** {tmux_status}
📂 **Сессия:** `{TMUX_SESSION}`
🤖 **Бот:** ✅ Работает

⚡ **Доступные команды:**
• `/send <команда>` - отправить команду
• `/tail [строки]` - последние строки
• `/screenshot` - текущее состояние
• `/status` - этот статус
"""
        await update.message.reply_text(status_msg, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка получения статуса: {str(e)}")

# --- Обработка кнопок быстрого доступа ---
async def handle_quick_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на кнопки быстрого доступа"""
    if not is_allowed(update):
        await update.message.reply_text("❌ Access denied.")
        return

    message_text = update.message.text

    # Обработка кнопок управления
    if message_text == "↩️ Enter":
        await send_key_command(update, "Enter")
    elif message_text == "⬇️ Down":
        await send_key_command(update, "Down")
    elif message_text == "⬅️ Left":
        await send_key_command(update, "Left")
    elif message_text == "➡️ Right":
        await send_key_command(update, "Right")
    elif message_text == "📄 /tail":
        await get_tail(update, context)
    elif message_text == "🔍 /screenshot":
        await get_screenshot(update, context)
    elif message_text == "🔄 /status":
        await get_status(update, context)
    elif message_text == "📊 /stats":
        await get_status(update, context)  # Используем ту же функцию что и для status
    elif message_text == "📜 /history":
        await get_tail(update, context)  # Показываем последние строки как историю
    elif message_text == "⚡ /buttons":
        await show_buttons(update, context)
    else:
        # Обрабатываем как обычную команду только если это не кнопка с эмодзи
        if not any(emoji in message_text for emoji in ["📄", "🔍", "📊", "↩️", "⬇️", "⬅️", "➡️", "🔄", "📜", "⚡"]):
            context.args = message_text.split()
            await send_command(update, context)
        else:
            await update.message.reply_text(f"⚠️ Неизвестная команда: {message_text}")

async def send_key_command(update: Update, key: str):
    """Отправка специальной клавиши"""
    try:
        cmd = ["tmux", "send-keys", "-t", TMUX_SESSION, SPECIAL_KEYS[key]]
        result = subprocess.run(cmd, capture_output=True, text=True, env=get_tmux_env(), timeout=10)
        
        if result.returncode == 0:
            await update.message.reply_text(f"✅ Клавиша {key} отправлена")
        else:
            error_msg = result.stderr or "Неизвестная ошибка"
            await update.message.reply_text(f"❌ Ошибка выполнения: {error_msg}")

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

# --- Показать кнопки ---
async def show_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать кнопки быстрого доступа"""
    if not is_allowed(update):
        await update.message.reply_text("❌ Access denied.")
        return

    reply_keyboard = create_reply_keyboard()
    welcome_msg = """🎛️ **Панель управления активна!**

🔧 **Быстрые кнопки:**
• **↩️ Enter** - отправить Enter
• **⬇️ Down** - стрелка вниз  
• **⬅️ Left** - стрелка влево
• **➡️ Right** - стрелка вправо

📋 **Команды:**
• **📄 /tail** - показать последние строки
• **🔍 /screenshot** - текущее состояние терминала
• **🔄 /status** - статус системы

💡 **Совет:** Кнопки всегда доступны на панели ввода!"""

    await update.message.reply_text(
        welcome_msg, 
        parse_mode="Markdown",
        reply_markup=reply_keyboard
    )

# --- Обработчик /start ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        await update.message.reply_text("❌ Access denied.")
        return

    reply_keyboard = create_reply_keyboard()
    welcome_msg = """🤖 **Telegram Terminal Bot запущен!**

✅ **Подключение к терминалу активно**
🖥️ **Сессия tmux:** `{}`

⚡ **Быстрые команды доступны на кнопках ниже:**
• Используйте кнопки для управления терминалом
• Отправляйте команды напрямую в чат
• `/send <команда>` для отправки команд в терминал

🎯 **Готов к работе!**""".format(TMUX_SESSION)

    await update.message.reply_text(
        welcome_msg, 
        parse_mode="Markdown",
        reply_markup=reply_keyboard
    )

# Обработчик сигналов завершения
def signal_handler(signum, frame):
    print(f"🛑 Получен сигнал {signum}. Завершение работы...")
    from datetime import datetime
    shutdown_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    shutdown_message = f"""🛑 **Telegram Terminal Bot остановлен**

⏰ Время остановки: `{shutdown_time}`
⚠️ Статус: Недоступен
🔧 Причина: Получен сигнал завершения

Для перезапуска запустите бота вручную"""
    
    send_simple_notification(shutdown_message)
    sys.exit(0)

def main():
    print("🤖 Бот запущен. Ожидаю команды...")
    
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Отправляем уведомление о запуске
    from datetime import datetime
    startup_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    startup_message = f"""🤖 **Telegram Terminal Bot запущен!**

⏰ Время запуска: `{startup_time}`
✅ Статус: Готов к работе
🔧 Сессия: `{TMUX_SESSION}`

📱 Отправьте `/start` для получения кнопок управления"""
    
    send_simple_notification(startup_message)
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Обработчики команд
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("send", send_command))
    app.add_handler(CommandHandler("tail", get_tail))
    app.add_handler(CommandHandler("screenshot", get_screenshot))
    app.add_handler(CommandHandler("status", get_status))
    app.add_handler(CommandHandler("buttons", show_buttons))

    # Обработчик текстовых сообщений (для кнопок)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quick_buttons))

    try:
        app.run_polling()
    except KeyboardInterrupt:
        print("🛑 Получен сигнал остановки...")
        shutdown_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        shutdown_message = f"""🛑 **Telegram Terminal Bot остановлен**

⏰ Время остановки: `{shutdown_time}`
⚠️ Статус: Недоступен
🔧 Причина: Плановая остановка

Для перезапуска запустите бота вручную"""
        
        send_simple_notification(shutdown_message)
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        error_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        error_message = f"""❌ **Ошибка Telegram Terminal Bot**

⏰ Время: `{error_time}`
🔴 Ошибка: `{str(e)[:100]}...`
🔄 Перезапустите бота вручную для продолжения работы"""
        
        send_simple_notification(error_message)

if __name__ == "__main__":
    main()