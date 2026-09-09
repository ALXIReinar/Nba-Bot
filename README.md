# База для выполнения ТЗ

Написал функции для соединения с редис и БД. А также пару функций для демонстрации паттерна кода

## Что используется

**Python 3.12.8**

1. Для Redis - `redis.asyncio`
2. Для PostgreSQL - `asyncpg`
3. Для переменных окружения - `pydantic-settings`

## 1. Подготовка env

Создать `.env.bot` в корне проекта, там же где лежит `env.example`

> copy env.example .env.bot

Нужно подставить свои креды
- **PG_USER**
- **PG_PASSWORD**
- **PG_DB**

\+ Остальные, если отличаются от дефолтных(пары хост-порт)

## 2. Проверка зависимостей

Требуется Postgresql и Redis. Если нет локально установленных, воспользоваться докер образами(запустить docker-compose.yml)

Заполнить `services.pg_db.environment` блок в `docker-compose.yml` своими кредами из `.env.bot`

> docker compose up -d

## 3. Запуск бота

> python -m core.main
