# AI Analyst

AI Analyst is a web application for evidence-backed analysis of business data. This repository currently contains Stage 1 — Foundation: Angular, FastAPI, PostgreSQL, and Docker Compose.

## Run locally

1. Copy `.env.example` to `.env` and replace the local database password.
2. Start the stack:

   ```powershell
   docker compose up --build
   ```

3. Open `http://localhost:4200`. The landing page calls `/api/health` through Nginx, which proxies to FastAPI. The same endpoint is available directly at `http://localhost:8000/api/health`.

Stop services with `docker compose down`. Add `--volumes` only when you intentionally want to remove local PostgreSQL data.

## Verify without Docker

Frontend (Node.js 20.19+, 22.12+, or 24+):

```powershell
cd frontend
npm ci
npm run build
npm test
```

Backend (Python 3.12+):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

Set `DATABASE_URL` before running the backend outside Compose. The health endpoint returns HTTP 503 and `database: "unavailable"` if PostgreSQL cannot be reached.

## Layout

- `frontend/` — Angular standalone application.
- `backend/` — FastAPI application, SQLAlchemy database boundary, and Alembic configuration.
- `infra/` — reverse-proxy configuration used by the frontend image.
- `docs/` — requirements and continuity journal.
