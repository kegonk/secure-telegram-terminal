#!/bin/bash

echo "🤖 Запуск Telegram Terminal Bot для локальной системы..."

# Проверяем наличие tmux
if ! command -v tmux &> /dev/null; then
    echo "❌ tmux не установлен! Установите tmux:"
    echo "Ubuntu/Debian: sudo apt install tmux"
    echo "CentOS/RHEL: sudo yum install tmux"
    echo "macOS: brew install tmux"
    exit 1
fi

# Проверяем наличие Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 не установлен!"
    exit 1
fi

# Проверяем файл .env
if [ ! -f ".env" ]; then
    echo "❌ Файл .env не найден!"
    echo "Создайте файл .env с настройками:"
    echo "BOT_TOKEN=your_bot_token_here"
    echo "ALLOWED_CHAT_ID=your_chat_id_here"
    exit 1
fi

# Создаем директории если их нет
mkdir -p logs
mkdir -p data

# Если venv поврежден (например, после неудачного создания), пересоздаем его
if [ -d "venv" ] && [ ! -f "venv/bin/activate" ]; then
    echo "⚠️ Найдено поврежденное виртуальное окружение. Пересоздание..."
    rm -rf venv
fi

# Создаем виртуальное окружение если его нет
if [ ! -d "venv" ]; then
    echo "🔧 Создание виртуального окружения..."
    if ! python3 -m venv venv; then
        echo "❌ Не удалось создать venv."
        echo "Установите пакет python3-venv и повторите запуск:"
        echo "sudo apt install python3-venv"
        exit 1
    fi
fi

# Активируем виртуальное окружение
echo "🔧 Активация виртуального окружения..."
if [ ! -f "venv/bin/activate" ]; then
    echo "❌ Виртуальное окружение повреждено (нет venv/bin/activate)."
    echo "Удалите папку venv и запустите скрипт снова."
    exit 1
fi
source venv/bin/activate

# Устанавливаем зависимости только при первом запуске или изменении requirements.txt
REQ_HASH_FILE="venv/.requirements.sha256"
REQ_HASH=$(sha256sum requirements.txt | awk '{print $1}')
INSTALLED_REQ_HASH=""
if [ -f "$REQ_HASH_FILE" ]; then
    INSTALLED_REQ_HASH=$(cat "$REQ_HASH_FILE")
fi
if [ "$REQ_HASH" != "$INSTALLED_REQ_HASH" ]; then
    echo "📦 Установка зависимостей..."
    if ! python3 -m pip install -r requirements.txt; then
        echo "❌ Не удалось установить зависимости."
        echo "Проверьте доступ к сети и наличие pip в Python."
        exit 1
    fi
    echo "$REQ_HASH" > "$REQ_HASH_FILE"
else
    echo "✅ Зависимости актуальны, установка не требуется"
fi

# Проверяем tmux сессию
TMUX_SESSION="claude"
if [ -f ".env" ]; then
    ENV_TMUX_SESSION=$(grep -E '^TMUX_SESSION=' .env | tail -n 1 | cut -d '=' -f2-)
    if [ -n "$ENV_TMUX_SESSION" ]; then
        TMUX_SESSION="$ENV_TMUX_SESSION"
    fi
fi
if [ -f "data/state.json" ]; then
    STATE_TMUX_SESSION=$(python3 - <<'PY'
import json
try:
    with open("data/state.json","r",encoding="utf-8") as f:
        data=json.load(f)
    value=data.get("tmux_session")
    if isinstance(value,str) and value.strip():
        print(value.strip())
except Exception:
    pass
PY
)
    if [ -n "$STATE_TMUX_SESSION" ]; then
        TMUX_SESSION="$STATE_TMUX_SESSION"
    fi
fi
if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
    echo "✅ tmux сессия '$TMUX_SESSION' уже существует"
else
    echo "🔧 Создание tmux сессии '$TMUX_SESSION' с bash..."
    SHELL=/bin/bash tmux new-session -d -s "$TMUX_SESSION" -c "$(pwd)"
    echo "✅ tmux сессия '$TMUX_SESSION' создана"
fi

# Настраиваем логирование tmux сессии
echo "📝 Настройка логирования tmux сессии..."
# Отключаем старое логирование если есть
tmux pipe-pane -t "$TMUX_SESSION"
# Настраиваем логирование с фильтром ANSI кодов  
tmux pipe-pane -t "$TMUX_SESSION" -o "sed -e 's/\x1b\[[0-9;]*m//g' -e 's/\x1b\[[0-9;]*[A-Za-z]//g' -e 's/\x1b\[[0-9]*[JK]//g' -e 's/\[?2004[lh]//g' >> logs/${TMUX_SESSION}_terminal.log"
echo "✅ Логирование настроено: logs/${TMUX_SESSION}_terminal.log"

# Запускаем бота
echo "🚀 Запуск бота..."
python3 bot.py
