# Opencode Skills & Config

Конфигурация навыков и MCP-серверов для opencode AI-агента.

## Установка

```bash
git clone https://github.com/penkovmm/opencode-config.git ~/opencode-config
cd ~/opencode-config
./setup.sh
```

Затем создай `~/.config/opencode/.env` с ключами:

```
OPENROUTER_API_KEY=sk-or-v1-...
OPENAI_API_KEY=sk-proj-...
OPENAI_PROXY=http://user:pass@host:port
```

## Что внутри

### Навыки (`skills/`)

| Навык | Описание | Модель |
|---|---|---|
| `vision` | Описание изображений, скриншотов, PDF. Smart routing: text PDF → pypdf, scan → Qwen3-VL | Qwen3-VL 235B |
| `vf-coder` | Визуальная отладка UI: скриншот → аудит → правка → перепроверка | Qwen3-VL 235B + chrome-devtools |
| `image-gen` | Генерация изображений через GPT Image 2 | GPT Image 2 (OpenAI) |
| `bootstrap` | Первичная настройка opencode на новом устройстве | — |

### MCP-серверы (`opencode.jsonc`)

- **chrome-devtools** — headless Chrome, изолированный профиль
- **web-search** — поиск в интернете

### Скрипты (`scripts/`)

- `vision.py` — универсальное зрение: describe, ask, review, pdf-table, pdf-create
- `image-gen.py` — генерация изображений через OpenAI API

## Обновление

```bash
cd ~/opencode-config && git pull
```

Навыки и скрипты обновятся автоматически (симлинки).
