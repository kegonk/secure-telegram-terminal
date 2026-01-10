#!/bin/bash

echo "🛑 Остановка Telegram Terminal Bot..."

# Находим и убиваем процесс бота
BOT_PID=$(pgrep -f "python.*bot.py")

if [ ! -z "$BOT_PID" ]; then
    kill $BOT_PID
    echo "✅ Бот остановлен (PID: $BOT_PID)"
    echo "$(date): Бот остановлен (PID: $BOT_PID)" >> logs/cron_bot.log
else
    echo "⚠️ Бот не запущен"
fi
