# 🤖 MM Bot (ServiceDesk)

Telegram бот для работы с ServiceDesk (Magnit/BMC Helix).

## Возможности

- 📊 База магазинов — загрузка и хранение Excel (.xlsx)
- 🔐 Авторизация в ServiceDesk
- 📋 Просмотр инцидентов
- 👥 Управление пользователями

## Команды

| Команда | Описание |
|---------|----------|
| `/start` | Активировать бота, показать кол-во магазинов |
| `/sd` | Авторизация в ServiceDesk |
| `/my` | Мои инциденты |
| `/listusers` | Список пользователей |
| `/adduser` | Добавить пользователя |

## Установка

### Локально

```bash
pip install -r requirements.txt
cp config.json.example config.json
# Отредактируйте config.json
python main.py
```

### Docker

```bash
docker compose up -d
```

## Настройка

### config.json

```json
{
  "bot_token": "YOUR_BOT_TOKEN",
  "admins": [123456789],
  "allowed": [123456789]
}
```

### Переменные окружения

- `BOT_TOKEN` — токен Telegram бота
- `TZ` — часовой пояс (по умолчанию UTC)

## Разработка

- Ветка `dev` — разработка
- Ветка `main` — production

### CI/CD

Деплой происходит автоматически:
- **dev** → при пуше в ветку `dev`
- **main** → при пуше в ветку `main`

## Структура файлов

```
├── main.py          # Основной код бота
├── servicedesk.py   # Модуль ServiceDesk API
├── config.json      # Конфигурация
├── docker-compose.yml
├── dockerfile
├── requirements.txt
└── ttf/             # Шрифты для PDF
```

## Лицензия

MIT
