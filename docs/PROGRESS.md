# AI Analyst — прогресс проекта

Последнее обновление: 2026-09-17.

## Текущее состояние

Stage 1 — Foundation завершён и проверен. Работает Docker Compose vertical slice:
Angular → `/api/health` → FastAPI → PostgreSQL connectivity check.

Контейнеры остаются запущенными локально: frontend на `http://localhost:4200`, backend на `http://localhost:8000`.
Текущий этап разработки: Stage 2 — Dataset ingestion, ещё не начат.

## С чего продолжить

1. Прочитать `AGENTS.md` и этот журнал, проверить `git status` и запущенные контейнеры: `docker compose ps`.
2. Начать только Stage 2: ограниченный CSV/XLSX upload, validation, parsing, schema detection и preview API/UI.
3. Сначала определить явные API-контракты и модель данных dataset; не переходить к LLM, agent или SQL tool.

Запуск: `docker compose up --build`. Остановка: `docker compose down`.

## Этапы

- [x] Сохранение исходного контекста и настройка журнала работы.
- [x] Stage 1 — Foundation: Angular 21, FastAPI, PostgreSQL, Docker Compose.
- [ ] Stage 2 — Dataset ingestion: CSV/XLSX, определение схемы, preview.
- [ ] Stage 3 — Basic AI: один LLM provider, structured output.
- [ ] Stage 4 — Agent: tool calling и собственный Agent Loop.
- [ ] Stage 5 — Analysis Tools: SQL, статистика, изолированный Python sandbox.
- [ ] Stage 6 — Visualization: structured charts и ECharts.
- [ ] Stage 7 — Explainability: evidence и Analysis Trace.
- [ ] Stage 8 — Production hardening: тесты, ошибки, безопасность, observability, deployment.

## Принятые договорённости

- Все файлы проекта находятся в текущей папке AI Analyst; дополнительная вложенная папка `ai-analyst/` не нужна.
- Полное исходное описание пользователя сохранено без изменений в `docs/PROJECT_CONTEXT.md`.
- Разработка идёт итеративно; не реализовывать весь продукт за один этап.
- LLM выбирает действия, вычисления выполняют backend tools. Python агента выполняется в отдельном sandbox.
- Analysis Trace показывает наблюдаемые действия, вычисления и результаты, а не скрытые рассуждения модели.
- Конкретные версии, LLM provider и детали реализации пока не выбраны.
- Пользователь поручил делать commit и push в GitHub после завершённых этапов.
- Пользователь попросил остановиться и сообщить, когда все модули проекта и готовый скрипт развёртывания будут завершены.

## GitHub

- Локальная ветка: `master`.
- Репозиторий: https://github.com/ArtemisGur/AI_Analyst.git.
- SSH-доступ отклонён GitHub (`Permission denied (publickey)`); для публикации используется HTTPS. Проверка доступа через HTTPS успешна, удалённых веток пока нет.
- Первый локальный commit документации: `f984b26`.
- Результат push проверяется по совпадению локального HEAD и удалённой ветки.

## История работы

### 2026-09-17 — Сохранение контекста

Выполнено:
- Осмотрена рабочая папка: существующего кода приложения нет.
- Сохранено исходное описание проекта в `docs/PROJECT_CONTEXT.md`.
- Создан `docs/PROGRESS.md` с этапами, текущим состоянием и точкой продолжения.
- Создан `AGENTS.md` с инструкцией читать и обновлять контекст во всех следующих сессиях проекта.

Проверки:
- Запуск приложения, build, tests и lint не выполнялись: код приложения ещё отсутствует.

Точка остановки: документация подготовлена; следующий шаг — Stage 1 — Foundation.

### 2026-09-17 — Stage 1: Foundation

Выполнено:
- Создан monorepo с `frontend/`, `backend/`, `infra/`, `docker-compose.yml`, `.env.example` и `README.md`.
- Создан Angular 21 standalone frontend с signal-first отображением состояния health API.
- Создан FastAPI backend с Pydantic Settings, SQLAlchemy engine, Alembic scaffold и endpoint `GET /api/health`.
- Health endpoint выполняет `SELECT 1` к PostgreSQL; при ошибке БД отвечает HTTP 503, а при успехе — `{ "status": "ok", "database": "connected" }`.
- Создан multi-stage frontend image: тесты и production build выполняются в Node 24, Nginx проксирует `/api/` к backend.
- Docker Compose поднимает PostgreSQL 17, backend и frontend; backend ждёт successful Postgres healthcheck.

Решения:
- Angular 21 выбран как текущая современная версия. Локальный Node 18 несовместим, поэтому воспроизводимые frontend install/test/build выполняются в Docker Node 24.
- SQLAlchemy используется синхронно только для первой health-проверки; async data layer и модели появятся ровно тогда, когда Stage 2 потребует операции с datasets.
- Nginx убирает необходимость в CORS для browser request и даёт тот же `/api` URL в контейнерной среде.
- Миграций данных пока нет; Alembic scaffold подготовлен до появления первой модели в Stage 2.

Проверки:
- `docker compose config --quiet` — успешно.
- `docker compose build frontend` — успешно; Angular unit tests: 2/2 passed; Angular production build: успешно.
- `backend/.venv/Scripts/python.exe -m pytest backend/tests -q` — 1 passed.
- `backend/.venv/Scripts/ruff.exe check backend` — успешно.
- `docker compose up -d` — все три контейнера running, PostgreSQL healthy.
- `curl http://localhost:8000/api/health` — `{ "status": "ok", "database": "connected" }`.
- `curl http://localhost:4200/api/health` — тот же успешный ответ через Nginx proxy.

Ограничения:
- В текущей Windows-среде Docker CLI работает через WSL и требует root / Docker daemon access. Команды README остаются обычными Docker Compose командами для настроенной пользовательской среды.
- Backend test выдаёт два upstream deprecation warning от Starlette/TestClient; тест проходит, код проекта не использует deprecated API напрямую.

Точка остановки: Stage 1 завершён. Следующий небольшой этап — Stage 2: CSV/XLSX upload, schema detection и preview.

## Формат следующих записей

Для каждого завершённого или прерванного этапа добавлять дату, выполненные изменения и файлы, решения с краткой причиной, команды проверок с результатами, оставшиеся проблемы и следующий конкретный шаг. Не заменять историю одной новой записью.
