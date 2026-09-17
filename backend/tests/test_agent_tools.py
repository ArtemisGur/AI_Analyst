from uuid import uuid4

import pytest

from app.agent.tools import ToolExecutionError, execute_dataset_tool
from app.datasets.models import Dataset


def test_dataset_summary_reads_source_file_and_calculates_statistics(tmp_path):
    source = tmp_path / "sales.csv"
    source.write_text("region,revenue\nNorth,10\nSouth,20\nSouth,\n", encoding="utf-8")
    dataset = Dataset(
        id=uuid4(),
        name="sales",
        original_filename="sales.csv",
        storage_path=str(source),
        media_type="text/csv",
        row_count=3,
        column_count=2,
        schema_metadata=[],
        preview=[],
    )

    tool = execute_dataset_tool(dataset, "dataset_summary", "{}")

    assert tool.result.row_count == 3
    assert tool.result.missing_counts["revenue"] == 1
    assert tool.result.numeric_statistics[0].mean == 15.0


def test_dataset_summary_rejects_arguments(tmp_path):
    source = tmp_path / "sales.csv"
    source.write_text("revenue\n10\n", encoding="utf-8")
    dataset = Dataset(
        id=uuid4(),
        name="sales",
        original_filename="sales.csv",
        storage_path=str(source),
        media_type="text/csv",
        row_count=1,
        column_count=1,
        schema_metadata=[],
        preview=[],
    )

    with pytest.raises(ToolExecutionError):
        execute_dataset_tool(dataset, "dataset_summary", '{"column":"revenue"}')


def test_grouping_orders_full_dataset_and_rejects_bad_arguments(tmp_path):
    import json

    source = tmp_path / "sales.csv"
    source.write_text("region,amount\n" + "\n".join(f"r{i},{i}" for i in range(30)))
    dataset = Dataset(storage_path=str(source))
    result = execute_dataset_tool(
        dataset,
        "group_by_metric",
        json.dumps({"group_by": "region", "metric": "amount", "order": "desc"}),
    ).result
    assert result["rows"][0] == {"region": "r29", "total": 29}
    assert result["total_groups"] == 30
    assert result["truncated"] is True
    for args in (
        "[]",
        "null",
        '{"group_by":[],"metric":"amount"}',
        '{"group_by":"region","metric":"region"}',
        '{"group_by":"region","metric":"amount","sql":"DROP"}',
    ):
        with pytest.raises(ToolExecutionError):
            execute_dataset_tool(dataset, "group_by_metric", args)


def test_grouping_preserves_missing_values(tmp_path):
    source = tmp_path / "sales.csv"
    source.write_text("region,amount\nNorth,\nSouth,2\n")
    result = execute_dataset_tool(
        Dataset(storage_path=str(source)),
        "group_by_metric",
        '{"group_by":"region","metric":"amount"}',
    ).result
    assert result["rows"][-1] == {"region": "North", "total": None}
