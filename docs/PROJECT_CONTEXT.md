# AI Analyst — Project Context

Ты выступаешь как senior full-stack / AI engineer и помогаешь мне разработать production-oriented AI-продукт **AI Analyst**.

Не нужно пытаться реализовать весь проект сразу. Двигайся итеративно: сначала изучай существующий код и архитектуру, затем предлагай небольшой план, после чего реализуй конкретный этап и проверяй результат.

## 1. Идея продукта

AI Analyst — веб-приложение, в которое пользователь загружает данные или подключает источник данных, после чего может задавать аналитические вопросы на естественном языке.

Пример:

> Почему в августе упала выручка?

Система должна не просто отправлять данные в LLM и получать текст.

AI Agent должен самостоятельно:

1. понять вопрос;
2. изучить структуру данных;
3. составить план анализа;
4. выбрать необходимые инструменты;
5. выполнить SQL/Python-анализ;
6. изучить результаты;
7. при необходимости выполнить дополнительные шаги;
8. построить графики;
9. сформировать вывод;
10. показать пользователю доказательства и ход анализа.

Главный принцип:

**LLM — мозг системы, но вычисления выполняются инструментами нашего backend.**

---

# 2. Основной пользовательский сценарий

Первый MVP:

User
→ загружает CSV/XLSX
→ видит preview данных
→ задаёт вопрос
→ AI Agent исследует dataset
→ выполняет необходимые вычисления
→ возвращает:

- текстовый вывод;
- key findings;
- KPI;
- таблицы;
- графики;
- использованные вычисления;
- SQL/Python;
- Analysis Trace.

Пример результата:

**Выручка в августе снизилась на 14%.**

Основные факторы:

- снижение продаж категории X;
- падение региона Y;
- уменьшение количества повторных клиентов.

Ниже пользователь должен иметь возможность посмотреть:

- графики;
- расчёты;
- SQL;
- Python;
- шаги агента;
- источники данных.

---

# 3. Технологический стек

## Frontend

Использовать:

- Angular 20+
- TypeScript
- Standalone API
- Signals
- RxJS там, где действительно нужен stream-based подход
- Reactive Forms
- ECharts
- REST API
- SSE для streaming результатов анализа

Предпочитать современный signal-first Angular.

Не использовать NgModules без необходимости.

Архитектура frontend должна позволять проекту масштабироваться, но не нужно преждевременно создавать огромное количество абстракций.

## Backend

Основной backend:

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic

## Database

- PostgreSQL

Позже:

- pgvector для RAG.

## Data processing

На первом этапе:

- Pandas

При необходимости позже:

- Polars.

## AI

LLM должен использоваться через API.

Архитектура не должна быть жёстко привязана к одному провайдеру.

Создать abstraction:

LLMProvider

В будущем должны быть возможны реализации:

- OpenAIProvider
- AnthropicProvider
- GeminiProvider
- LocalLLMProvider

Но в MVP реализуем только одного провайдера.

API keys никогда не должны попадать во frontend.

## Infrastructure

Для local development:

- Docker
- Docker Compose

Сервисы ориентировочно:

frontend
backend
postgres
python-sandbox

Позже могут появиться:

redis
worker
minio

Не добавлять их в MVP без реальной необходимости.

---

# 4. Архитектура

Высокоуровнево:

Angular App
↓
FastAPI
↓
Analysis Service
↓
Agent Engine
↓
LLM Provider

Agent Engine имеет доступ к tools:

- Dataset Inspector
- SQL Tool
- Python Tool
- Chart Tool
- Statistics Tool

Данные и состояние:

FastAPI
↔ PostgreSQL

Python-код должен выполняться отдельно:

Agent
↓
Python Tool
↓
isolated Python Sandbox

---

# 5. Agent Engine

Это центральная часть проекта.

Не использовать LangGraph сразу.

Сначала реализовать понятный собственный Agent Loop.

Пример:

User Question

↓

Agent получает:

- вопрос;
- schema dataset;
- metadata;
- доступные tools.

↓

LLM решает следующий action.

↓

Tool Call

↓

Tool Result

↓

результат снова передаётся Agent.

↓

Agent либо вызывает следующий tool, либо формирует final answer.

Условно:

while not finished:

    decision = llm(context)

    if decision.tool_call:
        result = execute_tool(decision.tool_call)
        context.add(result)

    else:
        return final_answer

Обязательно предусмотреть:

- max iterations;
- timeout;
- tool errors;
- invalid arguments;
- token/cost tracking;
- trace каждого шага.

---

# 6. Tools

Минимальный набор:

## inspect_dataset()

Возвращает общую информацию:

- rows;
- columns;
- missing values;
- detected types;
- sample;
- basic statistics.

## get_schema()

Возвращает структуру dataset.

Например:

orders

date: datetime
region: string
product: string
revenue: float
customer_id: string

## get_column_statistics()

Позволяет агенту получить статистику конкретных колонок.

## execute_sql()

Выполняет аналитические SELECT-запросы.

Важно:

AI не должен иметь возможность выполнять:

DROP
DELETE
UPDATE
INSERT
ALTER
TRUNCATE

SQL должен валидироваться.

## run_python()

Используется для:

- statistics;
- correlation;
- anomaly detection;
- transformations;
- сложных вычислений.

AI-generated Python НИКОГДА не выполнять внутри основного FastAPI process.

Использовать isolated sandbox/container.

Ограничить:

- execution time;
- CPU;
- RAM;
- filesystem;
- network.

## create_chart()

LLM не должен генерировать HTML.

Он возвращает structured chart specification.

Например:

{
  "type": "line",
  "title": "Revenue by month",
  "x": [...],
  "series": [...]
}

Angular преобразует эту структуру в ECharts.

---

# 7. Structured Output

LLM responses должны по возможности быть структурированными и валидироваться через Pydantic.

Не строить важную бизнес-логику на парсинге произвольного текста.

Пример FinalAnalysis:

{
  "summary": "...",
  "key_findings": [],
  "metrics": [],
  "charts": [],
  "tables": [],
  "evidence": [],
  "limitations": []
}

---

# 8. Analysis Trace

Это одна из ключевых функций продукта.

Каждый analysis должен сохранять trace.

Пример:

Analysis #182

Question:
"Почему упала выручка в августе?"

Steps:

✓ Inspect dataset

✓ Analyze monthly revenue

✓ Analyze regions

✓ Analyze products

✓ Compare customer segments

✓ Detect anomalies

✓ Generate charts

✓ Generate conclusion

Для каждого шага сохранять:

- step;
- tool;
- arguments;
- result summary;
- duration;
- token usage;
- estimated LLM cost;
- error, если возникла.

Пользователь должен иметь возможность открыть:

**How did AI get this?**

и увидеть доказательства вывода.

Не нужно показывать скрытые рассуждения модели. Показываем только наблюдаемые действия системы, tool calls, вычисления, данные и результаты.

---

# 9. Explainability

Каждый важный вывод AI желательно связывать с evidence.

Например:

"Revenue decreased by 14%."

Evidence:

monthly_revenue query
July: 1,200,000
August: 1,032,000

Пользователь должен иметь возможность проверить вывод.

AI Analyst должен отличаться от обычного chatbot именно этим.

---

# 10. Dataset ingestion

MVP поддерживает:

- CSV
- XLSX

Pipeline:

Upload
→ validation
→ parsing
→ normalization
→ schema detection
→ semantic type detection
→ statistics
→ preview
→ storage.

Нужно корректно обрабатывать:

- missing values;
- dates;
- numeric formats;
- strings;
- duplicated rows;
- invalid files;
- encoding;
- large files.

Но не переусложнять первую версию.

---

# 11. PostgreSQL integration

После CSV/XLSX MVP добавить подключение PostgreSQL пользователя.

Система должна:

- подключиться read-only credentials;
- получить schema;
- получить tables;
- получить columns;
- определить relationships;
- сохранить metadata;
- дать Agent возможность выполнять безопасные SELECT queries.

Никогда не давать AI write permissions.

---

# 12. RAG

RAG не нужен в самом первом MVP.

Добавить позже для бизнес-контекста.

Пример:

Компания загружает документ:

"Revenue = оплаченные заказы без VAT."

Документы:

→ parsing
→ chunking
→ embeddings
→ pgvector
→ retrieval
→ relevant context
→ Agent.

Таким образом Agent понимает не только цифры, но и внутренние определения компании.

---

# 13. Automatic Insights

После основной версии добавить background analysis.

Например ежедневно:

Data Snapshot
→ Trend Detection
→ Anomaly Detection
→ Change Detection
→ AI Explanation
→ Insight

Примеры:

"Conversion decreased by 14%."

"CAC increased by 21%."

"Enterprise revenue increased by 8%."

Пользователь сможет нажать:

Deep Analysis

и Agent проведёт полноценное исследование причины.

---

# 14. Reports

Позже добавить:

- Weekly Report
- Monthly Report
- Executive Summary

Report содержит:

- KPI;
- trends;
- charts;
- anomalies;
- explanations;
- risks;
- opportunities.

В перспективе:

- PDF export;
- PPTX export;
- shareable reports;
- scheduled reports.

---

# 15. Multi-tenancy

Не реализовывать полностью в первом MVP, но архитектура не должна мешать добавить:

Organization
→ Users
→ Data Sources
→ Datasets
→ Analyses
→ Reports

Будущие роли:

Admin
Analyst
Viewer

В production понадобятся:

- tenant isolation;
- RBAC;
- audit logs;
- secure secrets;
- dataset permissions.

---

# 16. Observability

Для каждого LLM interaction желательно сохранять:

- provider;
- model;
- prompt/version;
- latency;
- input tokens;
- output tokens;
- estimated cost;
- tool calls;
- errors.

Позже:

- OpenTelemetry;
- Grafana;
- evaluation system.

Стоимость AI — важная продуктовая метрика.

Архитектура должна позволять вычислять:

cost per analysis
cost per user
cost per organization

---

# 17. Model routing

Не использовать дорогую модель для каждого действия.

Архитектура в будущем должна позволять:

simple task
→ cheap/fast model

complex analysis
→ stronger model

Например простые операции:

- classification;
- SQL generation;
- formatting;
- summarization.

могут выполняться дешёвой моделью.

Deep Analysis может использовать более сильную модель.

Не реализовывать сложный router раньше времени, но не связывать систему намертво с одной моделью.

---

# 18. UX

Основные страницы MVP:

## Datasets

Список загруженных datasets.

## Dataset

Показывает:

- name;
- rows;
- columns;
- schema;
- preview;
- basic statistics.

Кнопка:

Analyze

## Analyst Workspace

Основной экран.

Пример layout:

Dataset

sales_2026.csv
128,340 rows

---

Ask your data

[ Why did revenue decrease in August? ]

[ Analyze ]

---

AI Analysis

Revenue ↓14%

Key findings

...

Charts

...

Evidence

...

[ How did AI get this? ]

## Analysis History

История предыдущих анализов.

---

# 19. Streaming

Анализ может занимать заметное время.

Не заставлять пользователя смотреть на spinner без информации.

Использовать SSE.

Frontend должен получать события примерно такого вида:

analysis.started

dataset.inspecting

tool.started

tool.completed

chart.created

analysis.generating_answer

analysis.completed

UI показывает прогресс анализа.

---

# 20. Security

Особенно внимательно относиться к:

- uploaded files;
- SQL execution;
- AI-generated Python;
- secrets;
- prompt injection;
- resource limits.

Основные правила:

- API keys только backend;
- PostgreSQL connections read-only;
- SQL validation;
- Python sandbox;
- network disabled/restricted в sandbox;
- execution timeout;
- file size limits;
- MIME/type validation;
- rate limits позже.

Не доверять LLM как security boundary.

---

# 21. Testing

Нужны:

Frontend:

- unit tests для важной логики;
- component tests там, где оправдано;
- Playwright для критических пользовательских сценариев.

Backend:

- pytest;
- API tests;
- Agent Tool tests;
- SQL validation tests;
- structured output validation.

Особенно важно тестировать Agent не только как обычный deterministic code.

Позже добавить evaluation dataset:

question
dataset
expected facts

и проверять, находит ли Agent необходимые факты.

---

# 22. MVP definition of done

Первый серьёзный milestone считается готовым, когда работает сценарий:

User uploads real CSV/XLSX

↓

System detects schema

↓

User sees preview

↓

User asks analytical question

↓

Agent creates analysis plan

↓

Agent autonomously uses tools

↓

SQL/Python performs calculations

↓

Agent creates structured charts

↓

Agent produces evidence-backed conclusion

↓

Angular displays:

- conclusion;
- key findings;
- KPI;
- charts;
- tables;
- evidence;
- Analysis Trace.

↓

User can inspect how result was calculated.

---

# 23. Что НЕ делать

Не нужно сейчас:

- обучать собственную LLM;
- делать fine-tuning;
- поднимать GPU infrastructure;
- использовать Kubernetes;
- делать multi-agent architecture ради самого multi-agent;
- подключать десятки data sources;
- создавать сложный microservice zoo;
- делать мобильное приложение;
- строить полноценный billing;
- реализовывать десятки типов charts.

Сначала нужен работающий vertical slice.

---

# 24. Принципы разработки

Следуй этим правилам:

1. Не переусложняй архитектуру.
2. Не создавай абстракции без причины.
3. Используй современные возможности Angular.
4. Соблюдай typing.
5. Backend contracts описывай явно.
6. Используй structured outputs.
7. Security boundaries не доверяй LLM.
8. AI-generated code всегда валидируй/изолируй там, где он выполняется.
9. Делай небольшие логичные commits.
10. После реализации проверяй результат.
11. Не меняй unrelated code.
12. Если существующий проект уже содержит решение задачи — сначала изучи его.
13. При архитектурном выборе кратко объясняй trade-offs.
14. Не добавляй библиотеку, если задача нормально решается стандартными средствами.
15. Код должен быть production-oriented, но MVP не должен превращаться в enterprise overengineering.

---

# 25. Как работать со мной

Я frontend developer и хорошо знаком с:

- Angular;
- TypeScript;
- Signals;
- RxJS;
- Reactive Forms;
- REST;
- GraphQL;
- WebSockets;
- Keycloak;
- Docker;
- Git;
- Linux.

Поэтому не нужно подробно объяснять базовый frontend.

Особое внимание уделяй тому, чему мне полезно научиться как будущему AI Full-Stack Engineer:

- Python backend;
- FastAPI;
- LLM APIs;
- structured outputs;
- tool calling;
- agent loops;
- context management;
- RAG;
- embeddings;
- vector databases;
- SQL safety;
- Python sandboxing;
- observability;
- AI evaluation;
- token/cost optimization;
- production AI architecture.

Когда реализуем AI-часть, объясняй не только **что написать**, но и **почему AI-система устроена именно так**.

---

# 26. Порядок разработки

Ориентировочно:

### Stage 1 — Foundation

Angular + FastAPI + PostgreSQL + Docker Compose.

### Stage 2 — Dataset ingestion

CSV/XLSX upload, parsing, schema detection, preview.

### Stage 3 — Basic AI

LLM provider + structured output.

### Stage 4 — Agent

Tool calling + Agent Loop.

### Stage 5 — Analysis Tools

SQL + statistics + Python sandbox.

### Stage 6 — Visualization

Structured charts + ECharts.

### Stage 7 — Explainability

Evidence + Analysis Trace.

### Stage 8 — Production hardening

Tests + errors + security + observability + deployment.

После этого:

PostgreSQL connections
→ RAG
→ Automatic Insights
→ Reports
→ Organizations
→ Billing.

---

# 27. Первая задача

Начни с **Stage 1 — Foundation**.

Если repository уже существует:

1. сначала полностью изучи его структуру;
2. определи используемые версии и существующие conventions;
3. не переписывай существующий код без необходимости;
4. покажи краткий план изменений;
5. затем реализуй foundation.

Если repository пустой:

создай минимальный production-oriented monorepo примерно следующего вида:

ai-analyst/

frontend/
backend/
infra/

docker-compose.yml
.env.example
README.md

Frontend:
Angular 20+.

Backend:
FastAPI + Pydantic + SQLAlchemy + Alembic.

Database:
PostgreSQL.

Нужно получить первый работающий vertical slice:

Angular
→ GET /api/health
→ FastAPI
→ PostgreSQL connectivity check.

Всё должно запускаться через Docker Compose.

После реализации:

1. запусти проект;
2. проверь build;
3. проверь tests;
4. проверь lint/type checking, если настроены;
5. проверь `/api/health`;
6. сообщи, какие файлы были изменены;
7. сообщи результаты проверок;
8. перечисли технические решения, которые были приняты;
9. предложи **только следующий логичный небольшой этап**, не реализуя его без команды.

Не начинай сразу писать Agent, RAG или другие поздние части проекта.

Сначала создай надёжный фундамент.