"""Bounded read-only SQL over one uploaded dataset; no application DB connection."""

import json
import os
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

SQL_TIMEOUT_SECONDS = 15
MAX_RESULT_BYTES = 64 * 1024


class SQLArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=8000)


SQL_TOOL = {
    "type": "function",
    "function": {
        "name": "execute_sql",
        "description": (
            "Run one read-only SQLite SELECT (non-recursive WITH supported) over the FULL selected "
            "file in table dataset. Use exact schema column names, double-quoted identifiers, "
            "single-quoted strings. Dates are ISO text; use substr(date_column,1,7) for months. "
            "Supports WHERE, GROUP BY, HAVING, ORDER BY, aggregates and window functions. "
            "For period changes compute 100.0*(new-old)/NULLIF(old,0). "
            "Returns at most 100 rows, 30 columns and 64 KiB; truncated results are marked. "
            "Use SQL for filtering, period comparisons and arithmetic; do not calculate in prose. "
            "No other tables, writes, PRAGMA, recursive CTEs, extensions or filesystem access."
        ),
        "parameters": SQLArguments.model_json_schema(),
    },
}


class SQLToolError(Exception):
    pass


def execute_sql(storage_path: str, arguments: dict) -> dict:
    request = SQLArguments.model_validate(arguments)
    # Only server-owned storage_path is accepted. The model supplies SQL, never a file path.
    payload = json.dumps({"path": str(Path(storage_path).resolve()), "query": request.query})
    env = os.environ.copy()
    env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", PYTHONIOENCODING="utf-8")
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "app.agent.sql_worker"],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=SQL_TIMEOUT_SECONDS,
            env=env,
            cwd=Path(__file__).resolve().parents[2],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired:
        raise SQLToolError("Превышен лимит времени SQL-анализа") from None
    except OSError:
        raise SQLToolError("SQL-инструмент временно недоступен") from None
    if completed.returncode or len(completed.stdout.encode("utf-8")) > MAX_RESULT_BYTES:
        raise SQLToolError("SQL-запрос отклонён или превысил лимиты ресурсов")
    try:
        result = json.loads(completed.stdout)
    except ValueError:
        raise SQLToolError("SQL-инструмент вернул некорректный результат") from None
    if "error" in result:
        raise SQLToolError("SQL-запрос отклонён. Проверьте SELECT, имена колонок и лимиты")
    return result
