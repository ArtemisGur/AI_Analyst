import json
from pathlib import Path

from pydantic import BaseModel

from app.datasets.models import Dataset
from app.datasets.service import parse_dataset

DATASET_SUMMARY_TOOL = {
    "type": "function",
    "function": {
        "name": "dataset_summary",
        "description": "Получает проверяемую сводку выбранного датасета. Аргументы не требуются.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}


class NumericStatistic(BaseModel):
    column: str
    non_null_count: int
    minimum: float | None
    maximum: float | None
    mean: float | None


class DatasetToolSummary(BaseModel):
    row_count: int
    column_count: int
    missing_counts: dict[str, int]
    numeric_statistics: list[NumericStatistic]


class ExecutedTool(BaseModel):
    name: str
    result: DatasetToolSummary
    trace_summary: str


class ToolExecutionError(Exception):
    pass


def execute_dataset_tool(dataset: Dataset, name: str, arguments: str) -> ExecutedTool:
    if name != "dataset_summary":
        raise ToolExecutionError("Запрошен неизвестный инструмент")
    try:
        if json.loads(arguments or "{}") != {}:
            raise ToolExecutionError("Инструмент не принимает аргументы")
    except json.JSONDecodeError as error:
        raise ToolExecutionError("Инструмент получил некорректные аргументы") from error
    try:
        frame = parse_dataset(
            Path(dataset.storage_path).read_bytes(), Path(dataset.storage_path).suffix.lower()
        )
    except OSError as error:
        raise ToolExecutionError("Файл датасета недоступен") from error
    statistics = []
    for column in frame.select_dtypes(include="number"):
        values = frame[column].dropna()
        statistics.append(
            NumericStatistic(
                column=str(column),
                non_null_count=int(values.count()),
                minimum=float(values.min()) if not values.empty else None,
                maximum=float(values.max()) if not values.empty else None,
                mean=round(float(values.mean()), 4) if not values.empty else None,
            )
        )
    result = DatasetToolSummary(
        row_count=len(frame),
        column_count=len(frame.columns),
        missing_counts={column: int(frame[column].isna().sum()) for column in frame.columns},
        numeric_statistics=statistics,
    )
    return ExecutedTool(
        name=name,
        result=result,
        trace_summary=(
            f"Получена сводка датасета: {len(frame)} строк, {len(frame.columns)} столбцов."
        ),
    )
