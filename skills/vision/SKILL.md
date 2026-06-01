---
name: vision
description: Описывает изображения, скриншоты, фото и PDF через Qwen3-VL (OpenRouter) или pypdf. Когда DeepSeek V4 не может прочитать визуальный файл — вызывает python3 vision.py describe. Поддерживает уточняющие вопросы, извлечение таблиц из PDF и создание PDF-документов.
allowed-tools: Bash(python3 /Users/penkovmm/.config/opencode/scripts/vision.py *)
---

# Vision — Универсальное зрение и работа с PDF

Ты DeepSeek V4 — текстовая модель, ты не видишь изображения. Когда попадается `.png`, `.jpg`, `.gif`, `.webp`, `.bmp` или PDF — **не пытайся читать сам**.

## Как использовать

### Описать изображение или PDF
```bash
python3 /Users/penkovmm/.config/opencode/scripts/vision.py describe "/path/to/file.png"
```
Возвращает текст + cache_id. PDF с текстовым слоем читается мгновенно через pypdf, сканы — через Qwen3-VL.

### Задать уточняющий вопрос (по кэшу, без повторной отправки)
```bash
python3 /Users/penkovmm/.config/opencode/scripts/vision.py ask <cache_id> "вопрос"
```

### Извлечь таблицы из PDF
```bash
python3 /Users/penkovmm/.config/opencode/scripts/vision.py pdf-table "/path/to/file.pdf" --csv
python3 /Users/penkovmm/.config/opencode/scripts/vision.py pdf-table "/path/to/file.pdf" --xlsx --output tables.xlsx
```

### Создать PDF из текста
```bash
python3 /Users/penkovmm/.config/opencode/scripts/vision.py pdf-create "## Заголовок\nТекст" --output report.pdf
```

## Правила
- Всегда используй `vision describe` для изображений и PDF — не пытайся читать их сам
- Для таблиц в PDF используй `pdf-table`, а не `describe`
- Для создания документов используй `pdf-create`
- cache_id из `describe` используй в `ask` для уточнений

## Таймауты
- Qwen3-VL 235B обрабатывает изображения до 120 секунд, особенно большие (>1 МБ, >2000px)
- **Перед вызовом всегда проверяй размер файла:** `ls -la /path/to/file.jpg`
- Если файл >500 КБ или разрешение >2000px → ставь таймаут **не менее 120 000 мс**
- Маленькие файлы (<500 КБ) → достаточно 60 000 мс
- PDF с текстовым слоем (pypdf) — мгновенно, таймаут не нужен
- PDF-скан (Qwen3-VL) — каждая страница как отдельное изображение, таймаут 120 000 мс
