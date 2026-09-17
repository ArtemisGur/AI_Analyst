import re
from io import BytesIO
from pathlib import Path

import pandas as pd
from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings

ALLOWED_SUFFIXES = {".csv", ".xlsx"}


def normalize_column_name(value: object, used_names: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_") or "column"
    candidate, index = base, 2
    while candidate in used_names:
        candidate = f"{base}_{index}"
        index += 1
    used_names.add(candidate)
    return candidate


def parse_dataset(content: bytes, suffix: str) -> pd.DataFrame:
    try:
        if suffix == ".xlsx":
            frame = pd.read_excel(BytesIO(content))
        else:
            for encoding in ("utf-8", "utf-8-sig", "cp1251"):
                try:
                    frame = pd.read_csv(BytesIO(content), encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("CSV encoding is not supported")
    except (ValueError, OSError, UnicodeError) as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid data file") from error
    if frame.empty and len(frame.columns) == 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Dataset has no columns")
    used_names: set[str] = set()
    frame.columns = [normalize_column_name(column, used_names) for column in frame.columns]
    return frame.convert_dtypes()


def json_value(value: object) -> object:
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value.item() if hasattr(value, "item") else value


def dataset_metadata(frame: pd.DataFrame) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    schema = [
        {"name": column, "dtype": str(frame[column].dtype), "missing_count": int(frame[column].isna().sum())}
        for column in frame.columns
    ]
    preview = [
        {column: json_value(value) for column, value in row.items()}
        for row in frame.head(20).to_dict(orient="records")
    ]
    return schema, preview


async def read_upload(file: UploadFile) -> tuple[bytes, str, str]:
    filename = file.filename or "dataset"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only CSV and XLSX files are supported")
    content = await file.read(get_settings().max_upload_bytes + 1)
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="File is empty")
    if len(content) > get_settings().max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File is too large")
    return content, filename, suffix
