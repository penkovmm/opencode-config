---
name: bootstrap
description: Первичная настройка окружения opencode на новом устройстве. Клонирует репозиторий конфигурации, устанавливает навыки, MCP-серверы, Python-зависимости и системные пакеты. Только для чистого устройства, один раз.
allowed-tools: Bash(git clone *) Bash(brew install *) Bash(pip install *) Bash(ln -sf *) Bash(mkdir *) Bash(cat *)
---

# Bootstrap — развёртывание opencode с нуля

## Предусловия
- macOS (через Homebrew)
- Установлен opencode
- Установлен git
- Клонируемый репозиторий: `https://github.com/penkovmm/opencode-config.git`

## Порядок

### 1. Системные зависимости
```bash
brew install poppler
```

### 2. Клонировать репозиторий
```bash
git clone https://github.com/penkovmm/opencode-config.git ~/opencode-config
```

### 3. Запустить setup.sh
```bash
cd ~/opencode-config && chmod +x setup.sh && ./setup.sh
```

### 4. Создать .env с ключами
```bash
cat > ~/.config/opencode/.env << 'EOF'
OPENROUTER_API_KEY=sk-or-v1-ЗАМЕНИ_НА_РЕАЛЬНЫЙ
OPENAI_API_KEY=sk-proj-ЗАМЕНИ_НА_РЕАЛЬНЫЙ
OPENAI_PROXY=http://user:pass@host:port
EOF
```

### 5. Создать рабочие папки
```bash
mkdir -p ~/.config/opencode/cache/vision
mkdir -p ~/.config/opencode/generated
```

## Проверка
```bash
python3 ~/.config/opencode/scripts/vision.py describe /tmp/test.pdf
python3 ~/.config/opencode/scripts/image-gen.py "test green square" --size 1024x1024
```

Обе команды должны выполниться без ошибок.

## Важно
- **Ключи в п.4 — заменить на реальные.** Запроси у пользователя, если не знаешь.
- Симлинки, не копирование. При `git pull` обновления подхватятся автоматически.
- Если opencode не установлен — `brew install opencode` или с [opencode.ai](https://opencode.ai)
