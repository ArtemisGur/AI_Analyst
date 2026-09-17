"""Disposable worker. Execute only SQLite bytecode authorized by a deny-by-default callback."""

import json
import math
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path

MAX_ROWS = 100
MAX_BYTES = 64 * 1024
MAX_VM_STEPS = 2_000_000
QUERY_SECONDS = 3
FUNCTIONS = frozenset(
    {
        "abs",
        "avg",
        "count",
        "sum",
        "total",
        "min",
        "max",
        "round",
        "coalesce",
        "ifnull",
        "nullif",
        "lower",
        "upper",
        "length",
        "trim",
        "ltrim",
        "rtrim",
        "substr",
        "substring",
        "replace",
        "like",
        "glob",
        "date",
        "datetime",
        "strftime",
        "julianday",
        "unixepoch",
        "row_number",
        "rank",
        "dense_rank",
        "lag",
        "lead",
        "first_value",
        "last_value",
    }
)


def authorize(action, arg1, arg2, database, source):
    if action == sqlite3.SQLITE_SELECT:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ and arg1 == "dataset" and database in ("main", None):
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION and arg2 in FUNCTIONS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def query_frame(frame, query: str) -> dict:
    # This process-global SQLite heap cap is set only inside the disposable worker.
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.execute("PRAGMA hard_heap_limit=67108864")
        connection.execute("PRAGMA temp_store=MEMORY")
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1024 * 1024)
        frame.to_sql("dataset", connection, index=False, chunksize=500)
        connection.execute("PRAGMA query_only=ON")
        for category, limit in (
            (sqlite3.SQLITE_LIMIT_SQL_LENGTH, 8000),
            (sqlite3.SQLITE_LIMIT_COLUMN, 30),
            (sqlite3.SQLITE_LIMIT_EXPR_DEPTH, 30),
            (sqlite3.SQLITE_LIMIT_COMPOUND_SELECT, 5),
            (sqlite3.SQLITE_LIMIT_VDBE_OP, 25000),
            (sqlite3.SQLITE_LIMIT_ATTACHED, 0),
            (sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 0),
        ):
            connection.setlimit(category, limit)
        connection.set_authorizer(authorize)
        deadline = time.monotonic() + QUERY_SECONDS
        steps = 0

        def interrupt():
            nonlocal steps
            steps += 1000
            return steps > MAX_VM_STEPS or time.monotonic() > deadline

        connection.set_progress_handler(interrupt, 1000)
        # execute (not executescript) enforces a single statement; SQLite itself parses SQL.
        cursor = connection.execute(query)
        if cursor.description is None:
            raise ValueError("A SELECT result is required")
        rows = []
        truncated = False
        for row in cursor:
            if len(rows) == MAX_ROWS:
                truncated = True
                break
            if any(
                isinstance(value, bytes) or (isinstance(value, float) and not math.isfinite(value))
                for value in row
            ):
                raise ValueError("Non-JSON result")
            rows.append(list(row))
        result = {
            "columns": [column[0] for column in cursor.description],
            "rows": rows,
            "returned_rows": len(rows),
            "truncated": truncated,
            "source_rows": len(frame),
        }
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode("utf-8")) > MAX_BYTES:
            raise ValueError("Result too large; aggregate or filter data")
        return result


def main():
    # Linux deployment: bound worker address space and CPU, including file parsing.
    if sys.platform == "linux":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    try:
        from app.core.config import get_settings
        from app.datasets.service import parse_dataset

        request = json.loads(sys.stdin.read(20000))
        query = request["query"]
        if not isinstance(query, str) or not 0 < len(query.encode("utf-8")) <= 8000:
            raise ValueError("Invalid query")
        path = Path(request["path"])
        if path.suffix.lower() not in {".csv", ".xlsx"}:
            raise ValueError("Unsupported file")
        with path.open("rb") as source:
            content = source.read(get_settings().max_upload_bytes + 1)
        if len(content) > get_settings().max_upload_bytes:
            raise ValueError("File too large")
        frame = parse_dataset(content, path.suffix.lower())
        result = query_frame(frame, query)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except Exception:
        # Do not leak paths, SQL diagnostics, credentials or source data through errors.
        print('{"error":"query_rejected"}')


if __name__ == "__main__":
    main()
