from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.datasets import get_session
from app.core.config import get_settings
from app.db.base import Base
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path / "uploads"))
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def session():
        with Session(engine) as value:
            yield value

    app.dependency_overrides[get_session] = session
    with TestClient(app) as value:
        yield value
    app.dependency_overrides.clear()
    engine.dispose()


def upload(client, content=b"region,revenue\nNorth,12\nSouth,\n", name="sales.csv"):
    return client.post("/api/datasets", files={"file": (name, content)})


def test_upload_persists_and_can_be_retrieved(client):
    result = upload(client)
    assert result.status_code == 201
    data = result.json()
    assert data["row_count"] == 2
    assert data["preview"][1]["revenue"] is None
    assert data["schema_metadata"][1]["missing_count"] == 1
    assert "storage_path" not in data
    assert client.get(f"/api/datasets/{data['id']}").json() == data
    listing = client.get("/api/datasets").json()
    assert listing[0]["id"] == data["id"]
    assert "preview" not in listing[0]
    assert client.get("/api/datasets?offset=1").json() == []


def test_rows_endpoint_paginates_the_full_dataset(client):
    result = upload(client, b"region,revenue\nNorth,12\nSouth,13\nWest,14\n")
    dataset_id = result.json()["id"]
    first = client.get(f"/api/datasets/{dataset_id}/rows?limit=2").json()
    second = client.get(f"/api/datasets/{dataset_id}/rows?limit=2&offset=2").json()
    assert first == {
        "total_rows": 3,
        "offset": 0,
        "rows": [{"region": "North", "revenue": 12}, {"region": "South", "revenue": 13}],
    }
    assert second["rows"] == [{"region": "West", "revenue": 14}]


@pytest.mark.parametrize(
    ("name", "content", "status"),
    [
        ("file.csv", b"", 422),
        ("file.txt", b"x\n1", 415),
        ("file.xlsx", b"not a zip", 422),
        ("file.csv", b"a,b\n", 422),
        ("file.csv", b'a,b\n"unterminated', 422),
        ("file.csv", b"a\ninf", 422),
    ],
)
def test_invalid_files(client, name, content, status):
    assert upload(client, content, name).status_code == status
    assert client.get("/api/datasets").json() == []


def test_limits(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 4)
    assert upload(client).status_code == 413
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 1000)
    monkeypatch.setattr(get_settings(), "max_dataset_rows", 1)
    assert upload(client).status_code == 413
    monkeypatch.setattr(get_settings(), "max_dataset_rows", 100)
    monkeypatch.setattr(get_settings(), "max_dataset_columns", 1)
    assert upload(client).status_code == 413


def test_database_failure_removes_file(client, monkeypatch):
    def fail(_self):
        raise SQLAlchemyError("private connection details")

    monkeypatch.setattr(Session, "commit", fail)
    result = upload(client)
    assert result.status_code == 503
    assert "private" not in result.text
    from pathlib import Path

    assert list(Path(get_settings().upload_dir).iterdir()) == []
    assert client.get("/api/datasets").json() == []


def test_normalization_encoding_preview_and_filename(client):
    content = "Регион,Total!,Total?\n" + "Север,1,2\n" * 25
    result = upload(client, content.encode("cp1251"), "../sales.csv")
    assert result.status_code == 201
    data = result.json()
    assert data["original_filename"] == "sales.csv"
    assert data["row_count"] == 25
    assert len(data["preview"]) == 20
    assert list(data["preview"][0]) == ["регион", "total", "total_2"]


def test_csv_dates_and_xlsx_are_parsed(client):
    csv_result = upload(client, b"month,revenue\n2026-08-01,12\n2026-09-01,18\n")
    assert csv_result.status_code == 201
    assert csv_result.json()["schema_metadata"][0]["dtype"].startswith("datetime")
    assert csv_result.json()["preview"][0]["month"].startswith("2026-08-01")

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Region", "Revenue"])
    sheet.append(["North", 12])
    content = BytesIO()
    workbook.save(content)
    xlsx_result = upload(client, content.getvalue(), "sales.xlsx")
    assert xlsx_result.status_code == 201
    assert xlsx_result.json()["preview"][0] == {"region": "North", "revenue": 12}


def test_missing_and_invalid_ids(client):
    assert client.get(f"/api/datasets/{uuid4()}").status_code == 404
    assert client.get("/api/datasets/invalid").status_code == 422
    assert client.get("/api/datasets?limit=101").status_code == 422


def test_xlsx_expansion_limit(client, monkeypatch):
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("large.xml", "x" * 100)
    monkeypatch.setattr(get_settings(), "max_xlsx_uncompressed_bytes", 50)
    assert upload(client, stream.getvalue(), "data.xlsx").status_code == 413
