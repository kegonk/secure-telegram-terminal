# Локальная установка и запуск Telegram Terminal Bot

## Требования

1. **Python 3.7+**
2. **tmux** - для создания сессий терминала
3. **curl** - для отправки уведомлений

## Установка зависимостей

### Ubuntu/Debian:
```bash
sudo apt update
sudo apt install tmux curl python3 python3-pip
```

### CentOS/RHEL:
```bash
sudo yum install tmux curl python3 python3-pip
```

### macOS:
```bash
brew install tmux curl python3
```

## Настройка

1. **Создайте файл .env** в корневой директории проекта:
```bash
BOT_TOKEN=your_bot_token_here
ALLOWED_CHAT_ID=your_chat_id_here
TMUX_SESSION=claude
LOG_FILE=logs/claude_terminal.log
```

2. **Получите токен бота:**
   - Напишите @BotFather в Telegram
   - Создайте нового бота командой `/newbot`
   - Скопируйте полученный токен в `.env`

3. **Получите ID чата:**
   - Напишите боту любое сообщение
   - Откройте `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Найдите значение `"id"` в разделе `"chat"`

## Запуск

### Автоматический запуск:
```bash
./start_local.sh
```

### Ручной запуск:
```bash
# Создание виртуального окружения (если нужно)
python3 -m venv venv

# Активация виртуального окружения
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Создание tmux сессии (если не существует)
tmux new-session -d -s claude

# Запуск бота
python bot.py
```

## Использование

После запуска бота:

1. Отправьте `/start` в Telegram чате
2. Используйте кнопки быстрого доступа или команды:
   - `/send <команда>` - отправить команду в терминал
   - `/tail [строки]` - показать последние строки терминала
   - `/screenshot` - текущее состояние терминала
   - `/status` - статус системы

## Управление tmux сессией

```bash
# Подключиться к сессии
tmux attach -t claude

# Отключиться (Ctrl+B, затем D)
# или просто закрыть терминал

# Список сессий
tmux list-sessions

# Убить сессию
tmux kill-session -t claude
```

## Остановка бота

- В терминале с ботом: `Ctrl+C`
- Или отправьте `SIGTERM`: `kill <PID>`

## Логи

Логи сохраняются в:
- `logs/claude_terminal.log` - логи терминала
- `logs/bot.log` - логи бота
- `logs/commands.log` - история команд

## Автозапуск после перезагрузки

### Способ 1: SystemD (рекомендуется для Linux)

```bash
# Автоматическая настройка
./setup_autostart.sh

# Управление сервисом
sudo systemctl start telegram-terminal-bot    # Запуск
sudo systemctl stop telegram-terminal-bot     # Остановка
sudo systemctl status telegram-terminal-bot   # Статус
sudo journalctl -u telegram-terminal-bot -f   # Логи
```

### Способ 2: Crontab (альтернатива)

```bash
# Автоматическая настройка
./setup_cron_autostart.sh

# Управление
./start_bot_cron.sh  # Запуск
./stop_bot.sh        # Остановка
pgrep -f 'python.*bot.py'  # Проверка статуса
```

### Способ 3: Ручной автозапуск

Добавьте в `.bashrc` или `.profile`:
```bash
# Запуск бота при входе в систему
cd /путь/к/проекту && ./start_local.sh &
```

## Отличия локальной версии от Docker

- **Работает ЛОКАЛЬНО** (не через Docker)
- Использует стандартные пути tmux (вместо `/app/tmp`)
- Не требует Docker и docker-compose
- Работает напрямую с локальной системой
- Требует ручной установки зависимостей
- **НЕ запускается автоматически** без дополнительной настройки