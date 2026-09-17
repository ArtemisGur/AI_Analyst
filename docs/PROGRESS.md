# AI Analyst — прогресс проекта

Последнее обновление: 2026-09-17.

## Текущее состояние

Stage 1 — Foundation завершён и проверен. Работает Docker Compose vertical slice:
Angular → `/api/health` → FastAPI → PostgreSQL connectivity check.

Контейнеры остаются запущенными локально: frontend на `http://localhost:4200`, backend на `http://localhost:8000`.
Stage 2 — Dataset ingestion завершён и проверен. Работает загрузка CSV/XLSX, определение схемы, preview и русский UI.
Stage 3 — Basic AI завершён и проверен в живом сценарии через RelayModels. Реализован OpenAI-совместимый provider, строгий structured output и русский интерфейс вопроса к выбранному датасету.
Текущий этап разработки: Stage 4 — Agent.

## С чего продолжить

1. Прочитать `AGENTS.md` и этот журнал, проверить `git status` и запущенные контейнеры: `docker compose ps`.
2. Следующий небольшой этап: задать контракт безопасного backend-инструмента и реализовать `dataset_summary` для Agent Loop.
3. Не подключать SQL, Python sandbox или произвольное выполнение кода до отдельного этапа Analysis Tools.

Запуск: `docker compose up --build`. Остановка: `docker compose down`.

## Этапы

- [x] Сохранение исходного контекста и настройка журнала работы.
- [x] Stage 1 — Foundation: Angular 21, FastAPI, PostgreSQL, Docker Compose.
- [x] Stage 2 — Dataset ingestion: CSV/XLSX, определение схемы, preview.
- [x] Stage 3 — Basic AI: один LLM provider, structured output.
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

### 2026-09-17 — Сверка перед продолжением Stage 2

- Проверены текущие файлы и git: до обновления журнала рабочее дерево чистое; заготовка ingestion уже сохранена в commit `4ddbf96`, скрипты запуска — в `85c387c` и `7c5241d`. Более ранняя запись о незакоммиченных файлах Stage 2 устарела.
- В коде есть модель Dataset, migration, POST/GET `/api/datasets`, parsing и preview первых 20 строк. Это заготовка, завершённость и корректность пока не подтверждены тестами.
- Frontend пока показывает только health; тесты backend покрывают только health. Типизированные metadata-контракты, обработка ошибок хранения и полноценная проверка ingestion ещё требуют работы.
- Следующий небольшой шаг (запланирован): закончить backend-контракт загрузки и получения dataset, проверить parsing/validation/storage тестами; затем подключить UI и проверить полный сценарий в Docker.
- В этой сессии код не менялся; build и тесты не запускались.

### 2026-09-17 — Stage 2: backend ingestion

Реализовано:
- Добавлены явные Pydantic-контракты для полного dataset и облегчённого списка, а также `GET /api/datasets/{id}` с 404 для отсутствующего dataset.
- Upload API принимает только CSV/XLSX, очищает имя файла, ограничивает исходный размер, строки, колонки и распакованный размер XLSX; CSV читается в UTF-8/UTF-8 BOM/CP1251.
- Колонки нормализуются с устранением дублей; response содержит schema, missing counts и первые 20 строк preview. Пустые datasets, некорректные файлы и бесконечные числа отклоняются.
- При ошибке хранилища транзакция откатывается, а уже созданный upload-файл удаляется. В list API добавлены limit/offset.
- Скрипты запуска больше не содержат абсолютный путь к локальной пользовательской папке: путь вычисляется относительно каталога проекта. `.env`, логи, uploads и Ruff cache исключены из Git.

Проверено:
- `backend/.venv/Scripts/ruff.exe check backend` — успешно.
- `backend/.venv/Scripts/python.exe -m pytest backend/tests -q` — 13 passed. Остаются внешние предупреждения Starlette/TestClient и Pandas при намеренно переданном `inf`.
- `docker compose up -d --build backend`, `GET /api/health` — успешно; живой `POST /api/datasets` с CSV вернул schema и preview. Созданный smoke-dataset и его файл затем удалены.

Точка продолжения: реализовать Angular UI datasets, затем выполнить финальную сквозную проверку Stage 2 и только после неё подготовить чистый commit/push.

### 2026-09-17 — Stage 2: frontend и завершение

Реализовано:
- Angular UI на русском языке: выбор CSV/XLSX, загрузка, русские состояния и ошибки, список dataset, schema и таблица preview.
- Добавлен безопасный синтетический файл `samples/sales_demo.csv` для проверки загрузки. Он содержит 18 строк продаж, даты и один пропуск; реальных пользовательских данных в репозитории нет.
- В API локализованы ошибки upload/storage. JSON-поля и коды ответов оставлены стабильными для frontend-контракта.

Проверено:
- `backend/.venv/Scripts/ruff.exe check backend` — успешно.
- `backend/.venv/Scripts/python.exe -m pytest backend/tests -q` — 14 passed; включены CSV, валидный XLSX, даты, лимиты, preview и ошибки.
- `docker compose build frontend` — Angular tests 2/2 passed и production build успешны.
- `docker compose up -d` — все контейнеры запущены, PostgreSQL healthy; health endpoint успешен через Nginx. Ошибка загрузки `.txt` через `http://localhost:4200/api/datasets` возвращается по-русски.

Решения и ограничения:
- Даты CSV распознаются для явных форматов `YYYY-MM-DD`, `YYYY/MM/DD`, `DD.MM.YYYY` и `DD-MM-YYYY`; неоднозначные строки остаются строками, чтобы не исказить исходные данные.
- Локальные `.env`, логи, uploads и cache исключены из Git. Скрипты запуска не содержат пользовательского имени или абсолютного пути.

Точка остановки: Stage 2 завершён. Следующий небольшой этап — Stage 3: Basic AI с одним провайдером и structured output, без Agent Loop.

### 2026-09-17 — Stage 3: Basic AI

Реализовано:
- Добавлен изолированный контракт `LLMProvider` и первая реализация `OpenAIProvider`; ключ, model и опциональный OpenAI-совместимый base URL считываются только из переменных окружения backend.
- Добавлен `POST /api/datasets/{dataset_id}/analysis`. Он передаёт провайдеру вопрос, схему и ограниченный preview выбранного датасета, а клиенту возвращает типизированные `summary`, `key_findings`, `limitations` и usage.
- Вызов OpenAI использует Responses API, строгую JSON Schema и `store=false`. Инструкции запрещают следовать командам из содержимого датасета и требуют отвечать по-русски с явными ограничениями.
- В Angular добавлена карточка вопроса и результата AI-анализа для выбранного датасета. Ключ не передаётся в браузер.
- Добавлены `.env.example`, Docker Compose-конфигурация и README с настройкой `OPENAI_API_KEY`; локальный `.env` не включён в Git.

Проверено:
- `backend/.venv/Scripts/ruff.exe check backend` — успешно.
- `backend/.venv/Scripts/python.exe -m pytest backend/tests -q` — 19 passed. Добавлена проверка RelayModels-ветки с `chat/completions`, JSON Schema и корректным чтением usage.
- `docker compose build frontend` — Angular tests 3/3 passed и production build успешны.
- Контролируемая проверка без ключа возвращает HTTP 503, без раскрытия конфигурации.
- Живой запрос к RelayModels с `OPENAI_BASE_URL=https://api.relaymodels.com/v1` и моделью `gpt-5.6-terra` успешен: API вернул структурированный ответ с выводом, наблюдениями, ограничениями и usage.

Решения и ограничения:
- Это Basic AI без Agent Loop и вычислительных инструментов: модель видит только metadata и preview, поэтому выводы ограничены этим контекстом.
- RelayModels использует OpenAI-совместимый `chat/completions`; прямой OpenAI-режим продолжает использовать Responses API. Для обоих ключ остаётся в локальном `.env` и не добавляется в коммиты или чат.

Точка продолжения: Stage 4 — Agent. Первый небольшой шаг: безопасный инструмент `dataset_summary` и контракт вызова инструмента.

### 2026-09-17 — Обновление дизайна datasets workspace

Реализовано:
- Переработан интерфейс datasets в стиле аналитического B2B-продукта: тёмная навигационная панель, рабочая область, компактная верхняя загрузка, карточки schema и таблица preview.
- Добавлены информативные состояния: доступность сервисов, число источников, готовность датасета к анализу, число строк/столбцов и подсветка пропусков.
- Реализован адаптивный layout: на узком экране панели переходят в одну колонку.
- Лимит Angular для component styles увеличен до 10/12 КБ, чтобы production build учитывал полный стиль страницы без предупреждений.

Проверено:
- `docker compose up -d --build frontend` — Angular tests 2/2 и production build успешно.
- Визуально проверен интерфейс в браузере на загруженном `sales_demo.csv`; отображаются dataset, schema и preview.

Точка продолжения: дизайн datasets готов. Следующий небольшой этап проекта остаётся прежним — Stage 3: Basic AI с одним провайдером и structured output.

### 2026-09-17 — Понятные типы столбцов в UI

Реализовано:
- Технические типы Pandas больше не отображаются в schema cards. UI переводит их в понятные пользователю значения: «Дата и время», «Целое число», «Число», «Да / нет» и «Текст».
- Визуальный акцент типа отделён от счётчика пропусков, поэтому карточки легче сканировать.

Проверено:
- `docker compose up -d --build frontend` — Angular tests 2/2 и production build успешно.
- В браузере проверено отображение дат, текста и nullable integers на загруженном CSV.

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

### 2026-09-17 — Stage 2: Dataset ingestion (в работе)

Уже добавлены, но ещё не проверены и не закоммичены: PostgreSQL-модель и Alembic migration для datasets, API-контуры загрузки и списка датасетов, безопасное чтение CSV/XLSX с размерным лимитом, нормализация имён колонок и сохранение preview/schema metadata.

Точка продолжения: завершить UI загрузки и preview, выполнить migration в Docker, добавить тесты parsing/upload API, затем собрать и проверить стек до commit/push.

## Формат следующих записей

Для каждого завершённого или прерванного этапа добавлять дату, выполненные изменения и файлы, решения с краткой причиной, команды проверок с результатами, оставшиеся проблемы и следующий конкретный шаг. Не заменять историю одной новой записью.
