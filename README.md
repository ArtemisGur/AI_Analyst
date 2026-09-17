# AI Analyst

AI Analyst — веб-приложение для аналитики бизнес-данных с проверяемыми выводами. Реализованы фундамент проекта, загрузка CSV/XLSX и первый AI-анализ с типизированным ответом.

## Запуск локально

1. Запустите из PowerShell:

   ```powershell
   .\scripts\start.ps1
   ```

   Скрипт создаст `.env` из `.env.example` при первом запуске. Задайте собственный пароль PostgreSQL в `.env` до публикации проекта.

2. Откройте `http://localhost:4200`. Frontend обращается к `/api/health` через Nginx, который проксирует запрос в FastAPI. Эндпоинт также доступен напрямую: `http://localhost:8000/api/health`.

Остановить сервисы можно командой `./scripts/stop.ps1`. Добавляйте флаг `--volumes` к Docker Compose только если намеренно хотите удалить локальные данные PostgreSQL и загруженные файлы.

## AI-анализ через OpenAI

Чтобы включить AI-анализ, добавьте в локальный `.env` собственный ключ:

```env
OPENAI_API_KEY=ваш_ключ
OPENAI_MODEL=gpt-5.5
```

Ключ используется только backend-контейнером и не передаётся в браузер. В OpenAI отправляются вопрос, схема датасета и ограниченный preview строк; полный загруженный файл не отправляется. Ответ имеет строгую структуру: вывод, ключевые наблюдения и ограничения. Без ключа интерфейс и загрузка датасетов доступны, а AI-анализ сообщит, что провайдер не настроен.

## Проверка без Docker

Frontend требует Node.js 20.19+, 22.12+ или 24+:

```powershell
cd frontend
npm ci
npm run build
npm test
```

Backend требует Python 3.12+:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

Перед запуском backend вне Docker задайте `DATABASE_URL`. При недоступности PostgreSQL health endpoint вернёт HTTP 503 и `database: "unavailable"`.

## Структура проекта

- `frontend/` — Angular standalone-приложение.
- `backend/` — FastAPI, SQLAlchemy, Alembic и бизнес-логика API.
- `infra/` — конфигурация Nginx для frontend-контейнера.
- `docs/` — требования к продукту и журнал прогресса между сессиями.
