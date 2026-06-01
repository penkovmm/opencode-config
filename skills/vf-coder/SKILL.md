---
name: vf-coder
description: Визуальная отладка веб-интерфейсов. Цикл: код → скриншот (chrome-devtools) → аудит (Qwen3-VL) → правка. Проверяет вёрстку, кликабельность, формы, переходы. Максимум 5 итераций.
allowed-tools: Bash(python3 /Users/penkovmm/.config/opencode/scripts/vision.py *)
---

# VF-Coder — Визуальная отладка UI

## Когда использовать
- Пользователь просит проверить вёрстку, дизайн, внешний вид страницы
- После генерации HTML/CSS — всегда делать хотя бы один проход аудита
- Пользователь говорит «проверь дизайн», «как выглядит», «посмотри страницу»

## Цикл отладки

```
1. Сгенерировать/исправить код
2. Запустить сервер: python3 -m http.server 8000 --directory .
3. Открыть страницу в chrome-devtools и сделать скриншот:
   chrome-devtools new_page http://localhost:8000
   chrome-devtools take_screenshot --filePath /tmp/vf_screenshot.png
4. Аудит:
   python3 /Users/penkovmm/.config/opencode/scripts/vision.py review /tmp/vf_screenshot.png "ожидаемый дизайн: ..."
5. Применить правки из отчёта
6. Проверить интерактивность: клики (chrome-devtools click), формы (fill)
7. Повторить с шага 2, максимум 5 итераций
```

## Правила
- Максимум 5 итераций
- Останавливаться когда аудит возвращает «PASS — no issues detected»
- После каждой итерации показывать: «Исправлено X проблем, осталось Y»
