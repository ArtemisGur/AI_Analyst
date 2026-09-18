from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ColumnMetadata(BaseModel):
    name: str
    dtype: str
    missing_count: int


class DatasetSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    original_filename: str
    row_count: int
    column_count: int
    created_at: datetime


class DatasetResponse(DatasetSummary):
    schema_metadata: list[ColumnMetadata]
    preview: list[dict[str, str | int | float | bool | None]]


class DatasetRows(BaseModel):
    total_rows: int
    offset: int
    rows: list[dict[str, str | int | float | bool | None]]
