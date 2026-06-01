---
name: image-gen
description: Генерирует изображения через GPT Image 2 (OpenAI). Использует прокси для доступа из РФ. Принимает описание — возвращает путь к PNG-файлу.
allowed-tools: Bash(python3 /Users/penkovmm/.config/opencode/scripts/image-gen.py *)
---

# Image Gen — Генерация изображений

## Когда использовать
- Пользователь просит создать логотип, иконку, иллюстрацию, мокап
- Нужно изображение для сайта, презентации, соцсетей
- Пользователь описывает визуальную идею

## Как использовать
```bash
python3 /Users/penkovmm/.config/opencode/scripts/image-gen.py "описание изображения" --size 1024x1024 --quality auto
```

## Параметры
- `--size`: 1024x1024, 1792x1024, 1024x1792 (по умолчанию: 1024x1024)
- `--quality`: low, medium, high, auto (по умолчанию: auto)
- `--output`: путь для сохранения (по умолчанию: ~/.config/opencode/generated/img_<hash>.png)

## Правила
- Сохранять изображения в понятное место (не в /tmp)
- Для нескольких изображений — разные имена файлов
- Между запросами — пауза 2 секунды (rate limit)
