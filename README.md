# AI Analyst

AI Analyst — веб-приложение для аналитики бизнес-данных с проверяемыми выводами. Сейчас реализованы фундамент проекта и начало загрузки датасетов: Angular, FastAPI, PostgreSQL, Docker Compose и API для CSV/XLSX.

## Запуск локально

1. Скопируйте `.env.example` в `.env` и задайте собственный пароль PostgreSQL для локальной среды.
2. Запустите стек:

   ```powershell
   docker compose up --build
   ```

3. Откройте `http://localhost:4200`. Frontend обращается к `/api/health` через Nginx, который проксирует запрос в FastAPI. Эндпоинт также доступен напрямую: `http://localhost:8000/api/health`.

Остановить сервисы можно командой `docker compose down`. Добавляйте флаг `--volumes` только если намеренно хотите удалить локальные данные PostgreSQL и загруженные файлы.

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
