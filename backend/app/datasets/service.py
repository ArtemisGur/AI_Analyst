import math
import re
from io import BytesIO
from pathlib import Path
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

import pandas as pd
from fastapi import HTTPException, UploadFile

from app.core.config import get_settings

ALLOWED_SUFFIXES = {".csv", ".xlsx"}
DATE_PATTERN = r"(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[./-]\d{1,2}[./-]\d{2,4})(?:[ T].*)?"


def normalize_column_name(value: object, used_names: set[str]) -> str:
    base = re.sub(r"[^\w]+", "_", str(value).strip().lower()).strip("_") or "column"
    candidate, index = base, 2
    while candidate in used_names:
        candidate = f"{base}_{index}"
        index += 1
    used_names.add(candidate)
    return candidate


def parse_dataset(content: bytes, suffix: str) -> pd.DataFrame:
    settings = get_settings()
    try:
        if suffix == ".xlsx":
            with ZipFile(BytesIO(content)) as archive:
                if sum(entry.file_size for entry in archive.infolist()) > (
                    settings.max_xlsx_uncompressed_bytes
                ):
                    raise HTTPException(413, "Распакованный XLSX превышает допустимый лимит")
            frame = pd.read_excel(BytesIO(content), nrows=settings.max_dataset_rows + 1)
        else:
            for encoding in ("utf-8", "utf-8-sig", "cp1251"):
                try:
                    frame = pd.read_csv(
                        BytesIO(content),
                        encoding=encoding,
                        nrows=settings.max_dataset_rows + 1,
                    )
                    break
                except UnicodeDecodeError:
                    continue
            else:
                    raise ValueError("Неподдерживаемая кодировка CSV")
    except (ValueError, OSError, UnicodeError, BadZipFile, KeyError, ParseError) as error:
        raise HTTPException(status_code=422, detail="Некорректный файл с данными") from error
    if frame.empty:
        raise HTTPException(422, "Датасет должен содержать хотя бы одну строку данных")
    if len(frame) > settings.max_dataset_rows or len(frame.columns) > settings.max_dataset_columns:
        raise HTTPException(413, "Датасет превышает лимит строк или столбцов")
    used_names: set[str] = set()
    frame.columns = [normalize_column_name(column, used_names) for column in frame.columns]
    frame = frame.convert_dtypes()
    for column in frame.select_dtypes(include="string"):
        values = frame[column].dropna()
        if not values.empty and values.astype(str).str.fullmatch(DATE_PATTERN).all():
            parsed = pd.to_datetime(values, format="mixed", dayfirst=True, errors="coerce")
            if parsed.notna().all():
                frame[column] = pd.to_datetime(frame[column], format="mixed", dayfirst=True)
    return frame


def json_value(value: object) -> object:
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    value = value.item() if hasattr(value, "item") else value
    if isinstance(value, float) and not math.isfinite(value):
        raise HTTPException(422, "Бесконечные числовые значения не поддерживаются")
    return value


def dataset_metadata(
    frame: pd.DataFrame,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    for column in frame.select_dtypes(include="number"):
        if frame[column].isin([float("inf"), float("-inf")]).any():
            raise HTTPException(422, "Бесконечные числовые значения не поддерживаются")
    schema = [
        {
            "name": column,
            "dtype": str(frame[column].dtype),
            "missing_count": int(frame[column].isna().sum()),
        }
        for column in frame.columns
    ]
    preview = [
        {column: json_value(value) for column, value in row.items()}
        for row in frame.head(20).to_dict(orient="records")
    ]
    return schema, preview


async def read_upload(file: UploadFile) -> tuple[bytes, str, str]:
    filename = (file.filename or "dataset").replace("\\", "/").rsplit("/", 1)[-1]
    if len(filename) > 255:
        raise HTTPException(422, "Имя файла превышает 255 символов")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(415, "Поддерживаются только файлы CSV и XLSX")
    content = await file.read(get_settings().max_upload_bytes + 1)
    if not content:
        raise HTTPException(422, "Файл пуст")
    if len(content) > get_settings().max_upload_bytes:
        raise HTTPException(413, "Размер файла превышает допустимый лимит")
    return content, filename, suffix
