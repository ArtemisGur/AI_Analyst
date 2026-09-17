from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.datasets.models import Dataset
from app.datasets.service import dataset_metadata, parse_dataset, read_upload
from app.db.session import engine

router = APIRouter(prefix="/datasets", tags=["datasets"])


class DatasetResponse(BaseModel):
    id: UUID
    name: str
    original_filename: str
    row_count: int
    column_count: int
    schema_metadata: list[dict[str, object]]
    preview: list[dict[str, object]]


def get_session():
    with Session(engine) as session:
        yield session


def response(dataset: Dataset) -> DatasetResponse:
    return DatasetResponse.model_validate(dataset, from_attributes=True)


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(file: UploadFile = File(...), session: Session = Depends(get_session)) -> DatasetResponse:
    content, filename, suffix = await read_upload(file)
    frame = parse_dataset(content, suffix)
    schema, preview = dataset_metadata(frame)
    upload_dir = Path(get_settings().upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    storage_path = upload_dir / f"{uuid4()}{suffix}"
    storage_path.write_bytes(content)
    dataset = Dataset(
        name=Path(filename).stem,
        original_filename=filename,
        storage_path=str(storage_path),
        media_type=file.content_type or "application/octet-stream",
        row_count=len(frame),
        column_count=len(frame.columns),
        schema_metadata=schema,
        preview=preview,
    )
    session.add(dataset)
    session.commit()
    session.refresh(dataset)
    return response(dataset)


@router.get("", response_model=list[DatasetResponse])
def list_datasets(session: Session = Depends(get_session)) -> list[DatasetResponse]:
    return [response(dataset) for dataset in session.scalars(select(Dataset).order_by(Dataset.created_at.desc()))]
