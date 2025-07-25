#!/bin/bash

echo "🔧 Настройка автозапуска Telegram Terminal Bot"

# Получаем текущего пользователя и путь к проекту
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

# Создаем systemd сервис
echo "🔧 Создание systemd сервиса..."
cat > telegram-terminal-bot.service << EOF
[Unit]
Description=Telegram Terminal Bot
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$PROJECT_PATH
Environment=PATH=$PROJECT_PATH/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStartPre=/bin/bash -c 'cd $PROJECT_PATH && python3 -m venv venv'
ExecStartPre=/bin/bash -c 'cd $PROJECT_PATH && ./venv/bin/pip install -q -r requirements.txt'
ExecStartPre=/bin/bash -c 'mkdir -p $PROJECT_PATH/logs'
ExecStartPre=/bin/bash -c 'tmux has-session -t claude 2>/dev/null || tmux new-session -d -s claude -c $PROJECT_PATH'
ExecStart=/bin/bash -c 'cd $PROJECT_PATH && source venv/bin/activate && python bot.py'
Restart=always
RestartSec=10
StandardOutput=append:$PROJECT_PATH/logs/bot.log
StandardError=append:$PROJECT_PATH/logs/bot_error.log

[Install]
WantedBy=multi-user.target
EOF

# Копируем сервис в системную директорию
echo "📋 Установка сервиса в systemd..."
sudo cp telegram-terminal-bot.service /etc/systemd/system/

# Перезагружаем systemd
echo "🔄 Перезагрузка systemd..."
sudo systemctl daemon-reload

# Включаем автозапуск
echo "⚡ Включение автозапуска..."
sudo systemctl enable telegram-terminal-bot.service

echo "✅ Автозапуск настроен!"
echo ""
echo "🎛️ Управление сервисом:"
echo "• Запуск:    sudo systemctl start telegram-terminal-bot"
echo "• Остановка: sudo systemctl stop telegram-terminal-bot"
echo "• Статус:    sudo systemctl status telegram-terminal-bot"
echo "• Логи:      sudo journalctl -u telegram-terminal-bot -f"
echo "• Отключить: sudo systemctl disable telegram-terminal-bot"
echo ""
echo "📝 Логи бота сохраняются в:"
echo "• $PROJECT_PATH/logs/bot.log"
echo "• $PROJECT_PATH/logs/bot_error.log"

# Предлагаем запустить сразу
read -p "🚀 Запустить бота сейчас? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo systemctl start telegram-terminal-bot
    echo "✅ Бот запущен!"
    sleep 2
    sudo systemctl status telegram-terminal-bot --no-pager
fi