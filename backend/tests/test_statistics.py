import json
import math

import numpy as np
import pandas as pd
import pytest

from app.agent.statistics import calculate_statistics
from app.agent.tools import ToolExecutionError, execute_dataset_tool
from app.datasets.models import Dataset


def test_known_distribution_outlier_and_correlation():
    frame = pd.DataFrame({"x": [1, 2, 3, 4, 100, None], "y": [2, 4, 6, 8, 200, 999]})
    result = calculate_statistics(frame, {"columns": ["x", "y"]})
    x = result.columns[0]
    assert (x.count, x.missing_count, x.mean, x.median, x.q1, x.q3) == (5, 1, 22, 3, 2, 4)
    assert x.sample_std == pytest.approx(math.sqrt(1902.5))
    assert (x.outlier_lower, x.outlier_upper, x.outlier_count) == (-1, 7, 1)
    assert x.outlier_examples[0].model_dump() == {"data_row": 5, "value": 100}
    assert sum(b.count for b in x.histogram) == 5
    assert result.correlations[0].pair_count == 5
    assert result.correlations[0].pearson == pytest.approx(1)
    json.dumps(result.model_dump(), allow_nan=False)


def test_missing_constant_small_samples_and_nonfinite_values():
    frame = pd.DataFrame(
        {
            "empty": [None] * 4,
            "constant": [7] * 4,
            "sparse": [1, None, np.inf, -np.inf],
            "x": [1, 2, 3, 4],
            "negative": [-1, -2, -3, -4],
        }
    )
    result = calculate_statistics(frame, {"columns": list(frame.columns)})
    empty, constant, sparse, _, _ = result.columns
    assert empty.count == 0 and empty.mean is None and empty.outlier_count is None
    assert constant.sample_std == 0 and constant.outlier_count == 0
    assert constant.histogram[0].count == 4
    assert sparse.nonfinite_count == 2 and sparse.missing_count == 1
    assert sparse.sample_std is None and sparse.outlier_count is None
    pairs = {(p.column_x, p.column_y): p for p in result.correlations}
    assert pairs["x", "negative"].pearson == pytest.approx(-1)
    assert pairs["constant", "x"].pearson is None
    assert pairs["sparse", "x"].pair_count == 1
    assert pairs["sparse", "x"].pearson is None
    json.dumps(result.model_dump(), allow_nan=False)


def test_reads_full_file_and_keeps_original_data_positions(tmp_path):
    source = tmp_path / "data.csv"
    source.write_text("value,label\n" + "1,a\n" * 30 + "100,z\n")
    tool = execute_dataset_tool(
        Dataset(storage_path=str(source)), "column_statistics", '{"columns":["value"]}'
    )
    assert tool.statistics.row_count == 31
    assert tool.statistics.columns[0].outlier_examples[0].data_row == 31
    assert tool.result == tool.statistics


@pytest.mark.parametrize(
    "args",
    [
        {"columns": []},
        {"columns": ["x"] * 2},
        {"columns": list("abcdef")},
        {"columns": ["unknown"]},
        {"columns": ["label"]},
        {"columns": ["flag"]},
        {"columns": ["date"]},
        {"columns": ["x"], "code": "print(1)"},
        {"columns": [1]},
        {"columns": "x"},
        {"columns": ["__import__('os')"]},
    ],
)
def test_statistics_rejects_invalid_columns_and_arguments(args):
    frame = pd.DataFrame(
        {"x": [1], "label": ["test"], "flag": [True], "date": pd.to_datetime(["2026-01-01"])}
    )
    with pytest.raises(ValueError):
        calculate_statistics(frame, args)


def test_outlier_example_limit_is_explicit():
    result = calculate_statistics(pd.DataFrame({"x": [0] * 100 + [100] * 11}), {"columns": ["x"]})
    column = result.columns[0]
    assert column.outlier_count == 11
    assert len(column.outlier_examples) == 10
    assert column.outliers_truncated is True


def test_numeric_overflow_fails_instead_of_reporting_false_statistics(tmp_path):
    source = tmp_path / "extreme.csv"
    source.write_text("x\n1e308\n-1e308\n1e308\n")
    with pytest.raises(ToolExecutionError):
        execute_dataset_tool(
            Dataset(storage_path=str(source)), "column_statistics", '{"columns":["x"]}'
        )


def test_xlsx_statistics(tmp_path):
    from openpyxl import Workbook

    path = tmp_path / "data.xlsx"
    book = Workbook()
    book.active.append(["value"])
    for value in [1, 2, 3, 4]:
        book.active.append([value])
    book.save(path)
    result = execute_dataset_tool(
        Dataset(storage_path=str(path)), "column_statistics", '{"columns":["value"]}'
    )
    assert result.statistics.columns[0].median == 2.5
