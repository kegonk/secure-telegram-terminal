#!/bin/bash

# Путь к проекту (будет заменен автоматически)
PROJECT_PATH="/mnt/d/bot_telegram_trminal_logs"
cd $PROJECT_PATH

# Логи
LOG_FILE="$PROJECT_PATH/logs/cron_bot.log"
ERROR_LOG="$PROJECT_PATH/logs/cron_bot_error.log"

# Создаем директории
mkdir -p logs

# Проверяем, не запущен ли уже бот
if pgrep -f "python.*bot.py" > /dev/null; then
    echo "$(date): Бот уже запущен" >> $LOG_FILE
    exit 0
fi

# Настраиваем tmux логирование
TMUX_SESSION="claude"
if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    # Отключаем старое логирование если есть
    tmux pipe-pane -t "$TMUX_SESSION"
    # Настраиваем логирование tmux сессии с фильтром ANSI кодов
    tmux pipe-pane -t "$TMUX_SESSION" -o "sed -e 's/\x1b\[[0-9;]*m//g' -e 's/\x1b\[[0-9;]*[A-Za-z]//g' -e 's/\x1b\[[0-9]*[JK]//g' -e 's/\[?2004[lh]//g' >> $PROJECT_PATH/logs/claude_terminal.log"
fi

# Активируем виртуальное окружение и запускаем бота
source venv/bin/activate
echo "$(date): Запуск бота через cron" >> $LOG_FILE
python bot.py >> $LOG_FILE 2>> $ERROR_LOG &

echo "$(date): Бот запущен с PID: $!" >> $LOG_FILE
