"""Deterministic descriptive statistics; no model-generated code or expressions."""

from itertools import combinations

import numpy as np
import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype
from pydantic import BaseModel, ConfigDict, Field, field_validator


class StatisticsArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    columns: list[str] = Field(min_length=1, max_length=5)

    @field_validator("columns")
    @classmethod
    def unique_columns(cls, columns):
        if any(not column or len(column) > 200 for column in columns):
            raise ValueError("Invalid column name")
        if len(set(columns)) != len(columns):
            raise ValueError("Duplicate columns")
        return columns


STATISTICS_TOOL = {
    "type": "function",
    "function": {
        "name": "column_statistics",
        "description": (
            "Calculate descriptive statistics, distributions, IQR outliers and pairwise Pearson "
            "correlations for 1-5 existing numeric columns over the FULL selected file. "
            "Returns count, missing/nonfinite counts, mean, median, quartiles, sample standard "
            "deviation (ddof=1), up to 10 histogram bins and 10 outlier examples per column. "
            "Outliers use Q1-1.5*IQR and Q3+1.5*IQR with linear quantiles, minimum 4 values. "
            "Pearson uses pairwise complete finite rows, minimum 3 pairs and nonconstant columns. "
            "Undefined statistics are null, not zero. Correlation is not causation; outliers are "
            "candidates for investigation, not proven errors. No filters: do not claim a subset."
        ),
        "parameters": StatisticsArguments.model_json_schema(),
    },
}


class FiniteModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class HistogramBin(FiniteModel):
    lower: float
    upper: float
    count: int


class OutlierExample(FiniteModel):
    data_row: int
    value: float


class ColumnStatistics(FiniteModel):
    column: str
    count: int
    missing_count: int
    nonfinite_count: int
    minimum: float | None = None
    maximum: float | None = None
    mean: float | None = None
    median: float | None = None
    q1: float | None = None
    q3: float | None = None
    sample_std: float | None = None
    histogram: list[HistogramBin] = Field(default_factory=list)
    outlier_lower: float | None = None
    outlier_upper: float | None = None
    outlier_count: int | None = None
    outlier_examples: list[OutlierExample] = Field(default_factory=list)
    outliers_truncated: bool = False
    notes: list[str] = Field(default_factory=list)


class Correlation(FiniteModel):
    column_x: str
    column_y: str
    pair_count: int
    pearson: float | None
    note: str | None = None


class StatisticsResult(FiniteModel):
    row_count: int
    columns: list[ColumnStatistics]
    correlations: list[Correlation]
    methods: list[str] = Field(
        default_factory=lambda: [
            "Все строки файла; пропуски и нечисловые бесконечные значения исключены из расчётов.",
            "Квартили: линейная интерполяция; стандартное отклонение выборочное (ddof=1).",
            "Интервалы распределения [нижняя, верхняя), последний включает верхнюю границу.",
            "Выбросы: за пределами Q1 − 1,5 IQR и Q3 + 1,5 IQR; минимум 4 значения.",
            "Номер строки — позиция записи в разобранном файле, начиная с 1, без заголовка.",
            "Пирсон: попарное исключение пропусков, минимум 3 пары. "
            "Корреляция не доказывает причину.",
            "Выбросы требуют проверки и не обязательно являются ошибками.",
        ]
    )


def calculate_statistics(frame: pd.DataFrame, arguments: dict) -> StatisticsResult:
    request = StatisticsArguments.model_validate(arguments)
    if len(frame) > 100_000:
        raise ValueError("Too many rows")
    clean = {}
    columns = []
    # Fail explicitly on numerical overflow instead of returning misleading NaN/Infinity.
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        for name in request.columns:
            if name not in frame.columns:
                raise ValueError("Unknown column")
            series = frame[name]
            if is_bool_dtype(series.dtype) or (
                not is_numeric_dtype(series.dtype) and not series.isna().all()
            ):
                raise ValueError("Numeric columns required")
            raw = series.to_numpy(dtype=float, na_value=np.nan)
            finite = np.isfinite(raw)
            values = raw[finite]
            clean[name] = raw
            column = ColumnStatistics(
                column=name,
                count=len(values),
                missing_count=int(series.isna().sum()),
                nonfinite_count=int((~finite & ~np.isnan(raw)).sum()),
            )
            columns.append(column)
            if not len(values):
                column.notes.append("Нет конечных числовых значений; статистика не определена.")
                continue
            q1, median, q3 = np.quantile(values, [0.25, 0.5, 0.75], method="linear")
            column.minimum, column.maximum = float(values.min()), float(values.max())
            column.mean, column.median = float(values.mean()), float(median)
            column.q1, column.q3 = float(q1), float(q3)
            if len(values) > 1:
                column.sample_std = float(values.std(ddof=1))
            else:
                column.notes.append("Для стандартного отклонения нужны минимум 2 значения.")
            if column.minimum == column.maximum:
                column.histogram = [
                    HistogramBin(lower=column.minimum, upper=column.maximum, count=len(values))
                ]
            else:
                counts, edges = np.histogram(values, bins=min(10, len(values)))
                column.histogram = [
                    HistogramBin(lower=float(edges[i]), upper=float(edges[i + 1]), count=int(count))
                    for i, count in enumerate(counts)
                ]
            if len(values) >= 4:
                iqr = q3 - q1
                low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                column.outlier_lower, column.outlier_upper = float(low), float(high)
                positions = np.flatnonzero(finite & ((raw < low) | (raw > high)))
                column.outlier_count = len(positions)
                column.outliers_truncated = len(positions) > 10
                column.outlier_examples = [
                    OutlierExample(data_row=int(index) + 1, value=float(raw[index]))
                    for index in positions[:10]
                ]
                if iqr == 0:
                    column.notes.append(
                        "IQR равен нулю: отклонения от квартилей требуют контекста."
                    )
            else:
                column.notes.append("Для поиска выбросов нужны минимум 4 значения.")
        correlations = []
        for x, y in combinations(request.columns, 2):
            valid = np.isfinite(clean[x]) & np.isfinite(clean[y])
            left, right = clean[x][valid], clean[y][valid]
            coefficient, note = None, None
            if len(left) < 3:
                note = "Недостаточно полных пар: требуется минимум 3."
            elif np.ptp(left) == 0 or np.ptp(right) == 0:
                note = "Корреляция не определена для постоянной колонки."
            else:
                coefficient = float(np.corrcoef(left, right)[0, 1])
            correlations.append(
                Correlation(
                    column_x=x, column_y=y, pair_count=len(left), pearson=coefficient, note=note
                )
            )
    return StatisticsResult(row_count=len(frame), columns=columns, correlations=correlations)
