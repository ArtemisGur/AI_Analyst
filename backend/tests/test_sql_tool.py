import json
import subprocess

import pytest

from app.agent.sql_tool import SQLToolError, execute_sql
from app.agent.tools import ToolExecutionError, execute_dataset_tool
from app.datasets.models import Dataset


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "sales.csv"
    path.write_text(
        "date,region,revenue\n" + "2026-05-01,North,10\n" * 20 + "2026-06-01,North,15\n" * 20,
        encoding="utf-8",
    )
    return str(path)


def test_sql_computes_period_change_over_full_file(source):
    query = """WITH monthly AS (
        SELECT substr(date,1,7) AS month, SUM(revenue) AS revenue
        FROM dataset WHERE region='North' GROUP BY month
    ), changes AS (
        SELECT month, revenue, LAG(revenue) OVER (ORDER BY month) AS previous FROM monthly
    ) SELECT month, revenue, ROUND(100.0*(revenue-previous)/NULLIF(previous,0),2)
      AS change_pct FROM changes ORDER BY month"""
    tool = execute_dataset_tool(
        Dataset(storage_path=source), "execute_sql", json.dumps({"query": query})
    )
    assert tool.result["rows"] == [["2026-05", 200, None], ["2026-06", 300, 50.0]]
    assert tool.result["source_rows"] == 40
    assert tool.sql_query == query
    assert tool.result["truncated"] is False


@pytest.mark.parametrize(
    "query",
    [
        "DELETE FROM dataset",
        "DROP TABLE dataset",
        "UPDATE dataset SET revenue=0",
        "INSERT INTO dataset VALUES ('2026', 'West', 1)",
        "CREATE TABLE secret(x)",
        "ATTACH DATABASE '/tmp/secret.db' AS secret",
        "PRAGMA table_info(dataset)",
        "SELECT * FROM sqlite_master",
        "SELECT * FROM analyses",
        "SELECT load_extension('/tmp/extension')",
        "SELECT readfile('/etc/passwd')",
        "SELECT * FROM pragma_table_info('dataset')",
        "SELECT 1; DELETE FROM dataset",
        "SELECT randomblob(100000000)",
        "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT * FROM c",
        "SELECT SUM(a.revenue) FROM dataset a, dataset b, dataset c, dataset d, dataset e",
    ],
)
def test_sql_rejects_forbidden_operations_and_resource_abuse(source, query):
    with pytest.raises(SQLToolError):
        execute_sql(source, {"query": query})


def test_sql_result_cap(source):
    result = execute_sql(source, {"query": "SELECT a.region FROM dataset a CROSS JOIN dataset b"})
    assert len(result["rows"]) == 100
    assert result["truncated"] is True


def test_sql_handles_nulls_and_quoted_values(tmp_path):
    path = tmp_path / "nulls.csv"
    path.write_text("region,revenue\nO'Brien,\nNorth,20\n", encoding="utf-8")
    result = execute_sql(
        str(path), {"query": "SELECT SUM(revenue), COUNT(*) FROM dataset WHERE region='O''Brien'"}
    )
    assert result["rows"] == [[None, 1]]


@pytest.mark.parametrize(
    "args",
    [
        {"query": ""},
        {"query": 123},
        {"query": "SELECT 1", "path": "/tmp/secret"},
        {"query": "x" * 8001},
    ],
)
def test_sql_arguments_cannot_override_source(source, args):
    with pytest.raises(ToolExecutionError):
        execute_dataset_tool(Dataset(storage_path=source), "execute_sql", json.dumps(args))


def test_sql_worker_timeout(source, monkeypatch):
    def timeout(*args, **kwargs):
        assert kwargs["timeout"] == 15
        raise subprocess.TimeoutExpired("worker", 15)

    monkeypatch.setattr("app.agent.sql_tool.subprocess.run", timeout)
    with pytest.raises(SQLToolError, match="времени"):
        execute_sql(source, {"query": "SELECT 1"})


def test_sql_limits_result_bytes_and_columns(source):
    with pytest.raises(SQLToolError):
        execute_sql(source, {"query": "SELECT '" + "a" * 1000 + "' FROM dataset a, dataset b"})
    with pytest.raises(SQLToolError):
        execute_sql(source, {"query": "SELECT " + ",".join("1" for _ in range(31))})


def test_sql_supports_xlsx_dates(tmp_path):
    from datetime import datetime

    from openpyxl import Workbook

    path = tmp_path / "sales.xlsx"
    workbook = Workbook()
    workbook.active.append(["date", "revenue"])
    workbook.active.append([datetime(2026, 6, 1), 42])
    workbook.save(path)
    result = execute_sql(
        str(path), {"query": "SELECT strftime('%Y-%m', date), SUM(revenue) FROM dataset GROUP BY 1"}
    )
    assert result["rows"] == [["2026-06", 42]]
