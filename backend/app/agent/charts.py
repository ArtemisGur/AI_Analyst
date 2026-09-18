"""Verified, bounded chart specifications computed from the selected dataset."""

import math
import re
from typing import Literal

import pandas as pd
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype
from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_CHART_POINTS = 24


class ChartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    type: Literal["line", "bar"]
    title: str = Field(min_length=1, max_length=150)
    group_by: str = Field(min_length=1, max_length=100)
    metrics: list[str] = Field(min_length=1, max_length=4)
    aggregation: Literal["sum", "mean"] = "sum"
    order: Literal["asc", "desc"] = "asc"
    time_granularity: Literal["none", "month"] = "none"

    @field_validator("metrics")
    @classmethod
    def metrics_must_be_unique(cls, metrics: list[str]) -> list[str]:
        if len(set(metrics)) != len(metrics) or any(not metric.strip() for metric in metrics):
            raise ValueError("metrics must be unique non-empty strings")
        return metrics


class ChartSeries(BaseModel):
    name: str
    values: list[float | None] = Field(min_length=1, max_length=MAX_CHART_POINTS)


class ChartSpec(BaseModel):
    type: Literal["line", "bar"]
    title: str = Field(min_length=1, max_length=150)
    x: list[str] = Field(min_length=1, max_length=MAX_CHART_POINTS)
    series: list[ChartSeries] = Field(min_length=1, max_length=4)
    source_rows: int = Field(ge=1)
    truncated: bool


CREATE_CHART_TOOL = {
    "type": "function",
    "function": {
        "name": "create_chart",
        "description": (
            "Creates a verified structured line or bar chart from the FULL selected file. "
            "Use exact column names. group_by is the category/date column; metrics are one to four "
            "numeric columns aggregated by sum or mean. For datetime columns, set time_granularity "
            "to month. Results have at most 24 points and are retained in the analysis trace for "
            "the UI. Do not invent chart values in the final answer."
        ),
        "parameters": ChartRequest.model_json_schema(),
    },
}


def create_chart(frame: pd.DataFrame, arguments: dict) -> ChartSpec:
    request = ChartRequest.model_validate(arguments)
    has_unknown_column = request.group_by not in frame.columns or any(
        metric not in frame.columns for metric in request.metrics
    )
    if has_unknown_column:
        raise ValueError("unknown chart column")
    if any(not is_numeric_dtype(frame[metric]) for metric in request.metrics):
        raise ValueError("chart metrics must be numeric")
    categories = frame[request.group_by]
    if request.time_granularity == "month":
        if not is_datetime64_any_dtype(categories):
            raise ValueError("month grouping requires a datetime column")
        categories = categories.dt.strftime("%Y-%m")
    grouped = frame.assign(_chart_group=categories).groupby("_chart_group", dropna=False)[
        request.metrics
    ]
    values = grouped.sum(min_count=1) if request.aggregation == "sum" else grouped.mean()
    if request.time_granularity == "month":
        values = values.sort_index()
    elif is_chronological_label_index(values.index):
        values = values.sort_index()
    else:
        values = values.sort_values(
            request.metrics[0], ascending=request.order == "asc", na_position="last"
        )
    visible = values.head(MAX_CHART_POINTS)
    labels = ["Нет значения" if pd.isna(label) else str(label) for label in visible.index]
    return ChartSpec(
        type=request.type,
        title=request.title,
        x=labels,
        series=[
            ChartSeries(name=metric, values=[finite_number(value) for value in visible[metric]])
            for metric in request.metrics
        ],
        source_rows=len(frame),
        truncated=len(values) > MAX_CHART_POINTS,
    )


def finite_number(value: object) -> float | None:
    if pd.isna(value) or not math.isfinite(float(value)):
        return None
    return float(value)


def is_chronological_label_index(index: pd.Index) -> bool:
    """Recognise ISO-like date labels so timeline charts remain chronological.

    Dataset authors often store a month bucket such as ``2026-08`` as text rather
    than a datetime column. The chart tool should still keep those values on a
    timeline instead of ordering them by a metric.
    """
    labels = index.dropna()
    if labels.empty or not all(isinstance(label, str) for label in labels):
        return False
    return all(
        re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])(?:-(0[1-9]|[12]\d|3[01]))?", label)
        for label in labels
    )
