import json
import math
from pathlib import Path

from fastapi import HTTPException
from pandas import isna
from pandas.api.types import is_numeric_dtype
from pydantic import BaseModel

from app.agent.sql_tool import SQLToolError, execute_sql
from app.agent.statistics import StatisticsResult, calculate_statistics
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
GROUP_BY_METRIC_TOOL = {
    "type": "function",
    "function": {
        "name": "group_by_metric",
        "description": "Суммирует числовую метрику по одному полю датасета.",
        "parameters": {
            "type": "object",
            "properties": {
                "group_by": {"type": "string"},
                "metric": {"type": "string"},
                "order": {"type": "string", "enum": ["asc", "desc"]},
            },
            "required": ["group_by", "metric"],
            "additionalProperties": False,
        },
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
    result: object
    trace_summary: str
    sql_query: str | None = None
    statistics: StatisticsResult | None = None


class ToolExecutionError(Exception):
    pass


def execute_dataset_tool(dataset: Dataset, name: str, arguments: str) -> ExecutedTool:
    try:
        parsed_arguments = json.loads(arguments or "{}")
    except json.JSONDecodeError as error:
        raise ToolExecutionError("Инструмент получил некорректные аргументы") from error
    if not isinstance(parsed_arguments, dict) or name not in {
        "dataset_summary",
        "group_by_metric",
        "execute_sql",
        "column_statistics",
    }:
        raise ToolExecutionError("Недопустимый инструмент или аргументы")
    if name == "execute_sql":
        try:
            result = execute_sql(dataset.storage_path, parsed_arguments)
        except (SQLToolError, ValueError) as error:
            raise ToolExecutionError("SQL-запрос отклонён или превысил лимиты") from error
        return ExecutedTool(
            name=name,
            result=result,
            sql_query=parsed_arguments["query"].strip(),
            trace_summary=(
                f"SQL-анализ по {result['source_rows']} строкам. "
                f"Получено строк результата: {result['returned_rows']}."
                + (" Результат ограничен первыми 100 строками." if result["truncated"] else "")
            ),
        )
    if name == "dataset_summary" and parsed_arguments:
        raise ToolExecutionError("Сводка не принимает аргументы")
    if name == "group_by_metric" and (
        set(parsed_arguments) - {"group_by", "metric", "order"}
        or not isinstance(parsed_arguments.get("group_by"), str)
        or not isinstance(parsed_arguments.get("metric"), str)
        or parsed_arguments.get("order", "asc") not in ("asc", "desc")
    ):
        raise ToolExecutionError("Недопустимые аргументы группировки")
    try:
        frame = parse_dataset(
            Path(dataset.storage_path).read_bytes(), Path(dataset.storage_path).suffix.lower()
        )
    except (OSError, HTTPException) as error:
        raise ToolExecutionError("Файл датасета недоступен") from error
    if name == "column_statistics":
        try:
            statistics = calculate_statistics(frame, parsed_arguments)
        except (ValueError, TypeError, ArithmeticError) as error:
            raise ToolExecutionError("Проверьте числовые колонки и диапазон значений") from error
        return ExecutedTool(
            name=name,
            result=statistics,
            statistics=statistics,
            trace_summary=f"Проверено {len(frame)} строк; колонок: {len(statistics.columns)}. "
            "Рассчитаны распределения, выбросы IQR и корреляции Пирсона.",
        )
    if name == "group_by_metric":
        group_by, metric = parsed_arguments.get("group_by"), parsed_arguments.get("metric")
        if group_by not in frame.columns or metric not in frame.columns:
            raise ToolExecutionError("В датасете нет выбранного поля")
        if not is_numeric_dtype(frame[metric]):
            raise ToolExecutionError("Метрика должна быть числовой")
        grouped = (
            frame.groupby(group_by, dropna=False)[metric]
            .sum(min_count=1)
            .sort_values(
                ascending=parsed_arguments.get("order", "asc") == "asc", na_position="last"
            )
        )
        result = {
            "group_by": group_by,
            "metric": metric,
            "total_groups": len(grouped),
            "truncated": len(grouped) > 20,
            "order": parsed_arguments.get("order", "asc"),
            "rows": [
                {group_by: str(key), "total": finite_number(value)}
                for key, value in grouped.head(20).items()
            ],
        }
        return ExecutedTool(
            name=name,
            result=result,
            trace_summary=f"Выполнена группировка {metric} по полю {group_by}.",
        )
    if name != "dataset_summary" or parsed_arguments != {}:
        raise ToolExecutionError("Недопустимые аргументы инструмента")
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


def finite_number(value):
    return None if isna(value) or not math.isfinite(float(value)) else float(value)
