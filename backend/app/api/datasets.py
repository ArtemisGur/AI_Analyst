from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.datasets.models import Dataset
from app.datasets.schemas import DatasetResponse, DatasetSummary
from app.datasets.service import dataset_metadata, parse_dataset, read_upload
from app.db.session import engine

router = APIRouter(prefix="/datasets", tags=["datasets"])


def get_session():
    with Session(engine) as session:
        yield session


def response(dataset: Dataset) -> DatasetResponse:
    return DatasetResponse.model_validate(dataset, from_attributes=True)


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> DatasetResponse:
    try:
        content, filename, suffix = await read_upload(file)
    finally:
        await file.close()
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(store_dataset, content, filename, suffix, session)


def store_dataset(content: bytes, filename: str, suffix: str, session: Session) -> DatasetResponse:
    frame = parse_dataset(content, suffix)
    schema, preview = dataset_metadata(frame)
    upload_dir = Path(get_settings().upload_dir)
    storage_path = upload_dir / f"{uuid4()}{suffix}"
    dataset = Dataset(
        name=Path(filename).stem,
        original_filename=filename,
        storage_path=str(storage_path),
        media_type=(
            "text/csv"
            if suffix == ".csv"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        row_count=len(frame),
        column_count=len(frame.columns),
        schema_metadata=schema,
        preview=preview,
    )
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
        storage_path.write_bytes(content)
        session.add(dataset)
        session.flush()
        result = response(dataset)
        session.commit()
    except (OSError, SQLAlchemyError):
        session.rollback()
        storage_path.unlink(missing_ok=True)
        raise HTTPException(503, "Хранилище датасетов временно недоступно") from None
    return result


@router.get("", response_model=list[DatasetSummary])
def list_datasets(
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[DatasetSummary]:
    query = (
        select(Dataset).order_by(Dataset.created_at.desc(), Dataset.id).limit(limit).offset(offset)
    )
    return [DatasetSummary.model_validate(dataset) for dataset in session.scalars(query)]


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset(dataset_id: UUID, session: Session = Depends(get_session)) -> DatasetResponse:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(404, "Датасет не найден")
    return response(dataset)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(dataset_id: UUID, session: Session = Depends(get_session)) -> None:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(404, "Датасет не найден")
    try:
        Path(dataset.storage_path).unlink(missing_ok=True)
        session.delete(dataset)
        session.commit()
    except (OSError, SQLAlchemyError):
        session.rollback()
        raise HTTPException(503, "Не удалось удалить датасет") from None
