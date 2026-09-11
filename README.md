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

## Тесты

Запустить тесты внутри Docker-контейнера:

```bash
docker compose exec api pytest -q
```

Успешный результат должен выглядеть примерно так:

```text
45 passed
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