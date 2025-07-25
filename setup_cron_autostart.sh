#!/bin/bash

echo "⏰ Настройка автозапуска через crontab"

CURRENT_USER=$(whoami)
PROJECT_PATH=$(pwd)

echo "👤 Пользователь: $CURRENT_USER"
echo "📁 Путь к проекту: $PROJECT_PATH"

# Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    echo "❌ Файл .env не найден!"
    echo "Создайте файл .env с настройками бота перед настройкой автозапуска"
    exit 1
fi

# Создаем скрипт-обертку для cron
echo "🔧 Создание скрипта для cron..."
cat > start_bot_cron.sh << 'EOF'
#!/bin/bash

# Путь к проекту (будет заменен автоматически)
PROJECT_PATH="PROJECT_PATH_PLACEHOLDER"
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

# Активируем виртуальное окружение и запускаем бота
source venv/bin/activate
echo "$(date): Запуск бота через cron" >> $LOG_FILE
python bot.py >> $LOG_FILE 2>> $ERROR_LOG &

echo "$(date): Бот запущен с PID: $!" >> $LOG_FILE
EOF

# Заменяем плейсхолдер на реальный путь
sed -i "s|PROJECT_PATH_PLACEHOLDER|$PROJECT_PATH|g" start_bot_cron.sh
chmod +x start_bot_cron.sh

# Создаем скрипт остановки
cat > stop_bot.sh << 'EOF'
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
EOF

chmod +x stop_bot.sh

# Создаем задание для crontab
CRON_JOB="@reboot $PROJECT_PATH/start_bot_cron.sh"

# Проверяем, есть ли уже такое задание
if crontab -l 2>/dev/null | grep -q "$PROJECT_PATH/start_bot_cron.sh"; then
    echo "⚠️ Задание cron уже существует"
else
    # Добавляем задание в crontab
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "✅ Задание добавлено в crontab"
fi

echo ""
echo "✅ Автозапуск через cron настроен!"
echo ""
echo "🎛️ Управление:"
echo "• Запуск:    ./start_bot_cron.sh"
echo "• Остановка: ./stop_bot.sh"
echo "• Статус:    pgrep -f 'python.*bot.py'"
echo "• Логи:      tail -f logs/cron_bot.log"
echo "• Ошибки:    tail -f logs/cron_bot_error.log"
echo ""
echo "📝 Crontab записи:"
crontab -l | grep bot

# Предлагаем запустить сразу
read -p "🚀 Запустить бота сейчас? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ./start_bot_cron.sh
    sleep 2
    if pgrep -f "python.*bot.py" > /dev/null; then
        echo "✅ Бот запущен!"
    else
        echo "❌ Ошибка запуска. Проверьте логи:"
        echo "tail logs/cron_bot_error.log"
    fi
fi