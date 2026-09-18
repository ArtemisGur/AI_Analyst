import json

import pytest

from app.agent.charts import create_chart
from app.agent.tools import ToolExecutionError, execute_dataset_tool
from app.datasets.models import Dataset


def test_chart_uses_all_rows_and_month_buckets(tmp_path):
    source = tmp_path / "sales.csv"
    source.write_text(
        "date,region,revenue,profit\n"
        "2026-05-01,North,10,4\n"
        "2026-05-15,South,20,6\n"
        "2026-06-01,North,15,5\n",
        encoding="utf-8",
    )
    tool = execute_dataset_tool(
        Dataset(storage_path=str(source)),
        "create_chart",
        json.dumps(
            {
                "type": "line",
                "title": "Выручка по месяцам",
                "group_by": "date",
                "metrics": ["revenue", "profit"],
                "time_granularity": "month",
            }
        ),
    )

    assert tool.chart is not None
    assert tool.chart.model_dump() == {
        "type": "line",
        "title": "Выручка по месяцам",
        "x": ["2026-05", "2026-06"],
        "series": [
            {"name": "revenue", "values": [30.0, 15.0]},
            {"name": "profit", "values": [10.0, 5.0]},
        ],
        "source_rows": 3,
        "truncated": False,
    }


def test_chart_limits_points_and_rejects_invalid_requests(tmp_path):
    source = tmp_path / "sales.csv"
    source.write_text(
        "region,revenue\n" + "\n".join(f"r{i},{i}" for i in range(30)), encoding="utf-8"
    )
    chart = execute_dataset_tool(
        Dataset(storage_path=str(source)),
        "create_chart",
        '{"type":"bar","title":"Revenue","group_by":"region","metrics":["revenue"],"order":"desc"}',
    ).chart
    assert chart is not None and len(chart.x) == 24 and chart.x[0] == "r29" and chart.truncated
    for arguments in (
        {"type": "pie", "title": "x", "group_by": "region", "metrics": ["revenue"]},
        {"type": "line", "title": "x", "group_by": "region", "metrics": ["region"]},
        {"type": "line", "title": "x", "group_by": "unknown", "metrics": ["revenue"]},
        {"type": "line", "title": "x", "group_by": "region", "metrics": ["revenue", "revenue"]},
    ):
        with pytest.raises(ToolExecutionError):
            execute_dataset_tool(
                Dataset(storage_path=str(source)), "create_chart", json.dumps(arguments)
            )


def test_chart_month_requires_datetime_column():
    import pandas as pd

    with pytest.raises(ValueError):
        create_chart(
            pd.DataFrame({"label": ["2026-05"], "revenue": [10]}),
            {
                "type": "line",
                "title": "x",
                "group_by": "label",
                "metrics": ["revenue"],
                "time_granularity": "month",
            },
        )
