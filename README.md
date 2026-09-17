# NavalBattle Service

REST-сервис для игры в морской бой.

## Стек

- Python 3.12
- FastAPI
- Uvicorn
- PostgreSQL 16
- SQLAlchemy 2
- Alembic
- Pytest
- Docker
- Docker Compose

## Структура проекта

```text
Internship/
├── alembic/             # миграции базы данных
├── app/                 # код FastAPI-приложения
├── tests/               # тесты
├── .dockerignore        # файлы, не попадающие в Docker image
├── .env.example         # пример переменных окружения
├── .gitignore           # файлы, не отслеживаемые Git
├── alembic.ini          # конфигурация Alembic
├── docker-compose.yml   # PostgreSQL + API
├── Dockerfile           # Docker image приложения
├── pytest.ini           # настройки Pytest
├── requirements.txt     # Python-зависимости
└── README.md
```

## Запуск проекта

Для запуска необходим Docker Desktop с поддержкой Linux-контейнеров.

Собрать и запустить проект:

```bash
docker compose up --build -d
```

Проверить состояние контейнеров:

```bash
docker compose ps
```

PostgreSQL должен иметь состояние `healthy`, а API должен быть запущен.

## API

После запуска Swagger доступен по адресу:

```text
http://localhost:8000/docs
```

### Начать игру

Первая игровая ручка:

```http
POST /game
```

Тело запроса отсутствует

При успешном создании игры сервис возвращает `201 Created`:

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "ships": [
    {
      "coordinates": ["A1", "A2", "A3", "A4"]
    }
  ]
}
```

При создании игры:

- генерируется валидная расстановка флота;
- создаётся уникальный `session_id` в формате UUID;
- игровая сессия сохраняется в PostgreSQL;
- сохраняются `session_id`, `status`, `ships` и `created_at`;
- новая сессия получает статус `active`.

При непредвиденной внутренней ошибке сервис возвращает
`500 Internal Server Error`:

```json
{
  "detail": "Internal Server Error"
}
```

## Тесты

Запустить тесты внутри Docker-контейнера:

```bash
docker compose exec api pytest -q
```

Успешный результат должен выглядеть примерно так:

```text
47 passed
```

## Остановка проекта

Остановить и удалить контейнеры:

```bash
docker compose down
```

При этом данные PostgreSQL в Docker volume сохранятся.

Если необходимо также удалить локальные данные PostgreSQL:

```bash
docker compose down -v
```