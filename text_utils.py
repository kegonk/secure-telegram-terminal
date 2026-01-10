import re

def clean_terminal_output(text: str) -> str:
    """
    Очистка терминального вывода от escape-последовательностей для лучшей читаемости
    """
    if not text:
        return text
    
    # Удаляем ANSI escape последовательности (расширенный паттерн)
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    text = ansi_escape.sub('', text)
    
    # Дополнительная очистка цветовых кодов
    text = re.sub(r'\[0[0-9];[0-9][0-9]m', '', text)  # [01;32m, [01;34m и т.д.
    
    # Удаляем все управляющие последовательности с квадратными скобками
    text = re.sub(r'\x1B\[[0-9;?]*[a-zA-Z]', '', text)  # Все ESC[ последовательности
    text = re.sub(r'\[\?[0-9]+[hl]', '', text)  # Режимы терминала без ESC
    text = re.sub(r'\[\?[0-9]+[;\d]*[hl]', '', text)  # Сложные режимы без ESC
    
    # Удаляем специфичные Claude Code последовательности (расширенный список)
    text = re.sub(r'\[38;5;\d+m', '', text)  # 256-color foreground
    text = re.sub(r'\[48;5;\d+m', '', text)  # 256-color background
    text = re.sub(r'\[39m', '', text)  # Default foreground
    text = re.sub(r'\[49m', '', text)  # Default background
    text = re.sub(r'\[22m', '', text)  # Normal intensity
    text = re.sub(r'\[2m', '', text)   # Dim/faint
    text = re.sub(r'\[7m', '', text)   # Reverse video
    text = re.sub(r'\[27m', '', text)  # Reverse video off
    text = re.sub(r'\[1m', '', text)   # Bold
    text = re.sub(r'\[0m', '', text)   # Reset
    
    # Удаляем позиционирование курсора (расширенный список)
    text = re.sub(r'\[\d*[ABCD]', '', text)  # Cursor movement
    text = re.sub(r'\[\d+;\d+[Hf]', '', text)  # Cursor position
    text = re.sub(r'\[2K', '', text)  # Clear line
    text = re.sub(r'\[1A', '', text)  # Cursor up
    text = re.sub(r'\[K', '', text)   # Clear to end of line
    text = re.sub(r'\[G', '', text)   # Cursor to column 1
    text = re.sub(r'\[\?25[lh]', '', text)  # Show/hide cursor
    text = re.sub(r'\[\?2004[hl]', '', text)  # Bracketed paste mode
    text = re.sub(r'\[\?1004[hl]', '', text)  # Focus events
    
    # Удаляем символы рамок Unicode и ASCII
    text = re.sub(r'[╭╮╰╯│─┐┘└┌├┤┬┴┼]', '', text)
    text = re.sub(r'[■□▪▫▲▼◆◇○●△▽]', '', text)
    text = re.sub(r'[─━│┃┄┅┆┇┈┉┊┋┌┍┎┏┐┑┒┓└┕┖┗┘┙┚┛├┝┞┟┠┡┢┣┤┥┦┧┨┩┪┫┬┭┮┯┰┱┲┳┴┵┶┷┸┹┺┻┼┽┾┿╀╁╂╃╄╅╆╇╈╉╊╋]', '', text)
    
    # Удаляем управляющие символы (сохраняем табы и переносы строк)
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    # Дополнительные паттерны для Claude Code интерфейса
    text = re.sub(r'╭[─]*╮', '', text)  # Верхние рамки
    text = re.sub(r'╰[─]*╯', '', text)  # Нижние рамки  
    text = re.sub(r'│.*?│', '', text)   # Содержимое между вертикальными линиями
    text = re.sub(r'> +[^ ]*', '>', text)  # Очистка промптов с лишними символами
    text = re.sub(r'\? for shortcuts', '', text)  # Удаляем подсказки
    
    # Очищаем повторяющиеся пробелы и переносы строк
    text = re.sub(r'\n\s*\n', '\n\n', text)  # Максимум 2 переноса подряд
    text = re.sub(r' +', ' ', text)  # Множественные пробелы в один
    
    # Фильтруем строки - оставляем только содержательные
    lines = text.split('\n')
    filtered_lines = []
    
    for line in lines:
        line = line.strip()
        # Пропускаем пустые строки и строки только из спецсимволов
        if not line:
            continue
        if re.match(r'^[>\s│─╭╮╰╯┐┘└┌├┤┬┴┼\[\]]+$', line):
            continue
        # Пропускаем строки только с одним символом
        if len(line) <= 1:
            continue
        filtered_lines.append(line)
    
    # Объединяем обратно
    text = '\n'.join(filtered_lines)
    
    # Удаляем пустые строки в начале и конце
    text = text.strip()
    
    return text

def format_for_telegram(text: str, max_length: int = 3500) -> str:
    """
    Форматирование текста для отправки в Telegram
    """
    # Очищаем от терминальных последовательностей
    clean_text = clean_terminal_output(text)
    
    # Обрезаем если слишком длинный
    if len(clean_text) > max_length:
        clean_text = clean_text[-max_length:]
        clean_text = "...\n" + clean_text
    
    # Если текст пустой после очистки
    if not clean_text.strip():
        return "📄 Терминальный вывод пуст или содержит только управляющие символы"
    
    return clean_text

def extract_user_input(text: str) -> str:
    """
    Извлечение пользовательского ввода из терминального вывода
    """
    lines = text.split('\n')
    user_lines = []
    
    for line in lines:
        # Ищем строки с промптом
        if '@' in line and ':' in line and '$' in line:
            # Извлекаем команду после $
            parts = line.split('$', 1)
            if len(parts) > 1 and parts[1].strip():
                user_lines.append(f"$ {parts[1].strip()}")
        # Ищем строки с вводом пользователя (не системные)
        elif line.strip() and not line.startswith('[') and not line.startswith('Script'):
            cleaned = clean_terminal_output(line)
            if cleaned.strip():
                user_lines.append(cleaned.strip())
    
    return '\n'.join(user_lines) if user_lines else ""

def format_claude_output(text: str) -> str:
    """
    Специальное форматирование для вывода Claude Code
    """
    clean_text = clean_terminal_output(text)
    
    # Ищем специфичные паттерны Claude Code
    if "Tips for getting started:" in clean_text:
        # Форматируем советы
        clean_text = re.sub(r'Tips for getting started:\s*', '💡 **Советы для начала работы:**\n', clean_text)
        clean_text = re.sub(r'(\d+\.)\s*', r'\n\1 ', clean_text)
        clean_text = re.sub(r'※ Tip:', '\n💡 **Совет:**', clean_text)
    
    if "cwd:" in clean_text:
        # Форматируем рабочую директорию
        clean_text = re.sub(r'cwd:\s*([^\s]+)', r'📁 **Рабочая директория:** `\1`', clean_text)
    
    # Удаляем артефакты интерфейса
    clean_text = re.sub(r'\? for shortcuts', '', clean_text)
    clean_text = re.sub(r'Try "write a test for <filepath>"', '', clean_text)
    
    return clean_text.strip()