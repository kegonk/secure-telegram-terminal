#!/bin/bash

echo "🔧 Настройка автозапуска Telegram Terminal Bot"

CURRENT_USER=$(whoami)
PROJECT_PATH=$(pwd)

echo "👤 Пользователь: $CURRENT_USER"
echo "📁 Путь: $PROJECT_PATH"

# Проверяем .env
if [ ! -f ".env" ]; then
    echo "❌ Файл .env не найден!"
    exit 1
fi

# Создаем директории, которые нужны systemd для append-логов
mkdir -p logs
mkdir -p data

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
ExecStartPre=/usr/bin/mkdir -p $PROJECT_PATH/logs $PROJECT_PATH/data
ExecStart=$PROJECT_PATH/start.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Устанавливаем сервис
echo "📋 Установка сервиса..."
sudo cp telegram-terminal-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable telegram-terminal-bot.service

echo "✅ Автозапуск настроен!"
echo ""
echo "🎛️ Управление:"
echo "• Запуск: sudo systemctl start telegram-terminal-bot"
echo "• Стоп:   sudo systemctl stop telegram-terminal-bot"
echo "• Статус: sudo systemctl status telegram-terminal-bot"
echo "• Логи:   tail -f logs/bot.log"
echo ""

read -p "🚀 Запустить сейчас? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo systemctl start telegram-terminal-bot
    echo "✅ Запущен!"
fi
