from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.analysis import get_llm_provider
from app.api.datasets import get_session
from app.datasets.models import Dataset
from app.db.base import Base
from app.llm.provider import GeneratedAnalysis, LLMProviderError
from app.llm.schemas import AnalysisContent, TokenUsage
from app.main import app


class FakeProvider:
    provider_name = "fake"

    async def analyze_dataset(self, dataset, question, execute_tool=None):
        assert dataset.name == "sales"
        assert question == "Что происходит с выручкой?"
        return GeneratedAnalysis(
            content=AnalysisContent(
                summary="В preview есть пропуск выручки.",
                key_findings=["Одна строка содержит пропуск."],
                limitations=["Доступен только preview датасета."],
            ),
            model="fake-model",
            usage=TokenUsage(input_tokens=12, output_tokens=7),
        )


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    dataset_id = uuid4()
    with Session(engine) as session:
        session.add(
            Dataset(
                id=dataset_id,
                name="sales",
                original_filename="sales.csv",
                storage_path="/data/uploads/sales.csv",
                media_type="text/csv",
                row_count=2,
                column_count=2,
                schema_metadata=[
                    {"name": "region", "dtype": "string", "missing_count": 0},
                    {"name": "revenue", "dtype": "Int64", "missing_count": 1},
                ],
                preview=[{"region": "North", "revenue": 12}, {"region": "South", "revenue": None}],
            )
        )
        session.commit()

    def session_dependency():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[get_llm_provider] = FakeProvider
    with TestClient(app) as value:
        yield value, dataset_id
    app.dependency_overrides.clear()
    engine.dispose()


def test_analysis_returns_structured_response(client):
    test_client, dataset_id = client
    response = test_client.post(
        f"/api/datasets/{dataset_id}/analysis",
        json={"question": "Что происходит с выручкой?"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "content": {
            "summary": "В preview есть пропуск выручки.",
            "key_findings": ["Одна строка содержит пропуск."],
            "limitations": ["Доступен только preview датасета."],
        },
        "provider": "fake",
        "model": "fake-model",
        "usage": {"input_tokens": 12, "output_tokens": 7},
        "analysis_trace": [],
    }


def test_analysis_validates_dataset_and_question(client):
    test_client, _ = client
    unknown = test_client.post(f"/api/datasets/{uuid4()}/analysis", json={"question": "Тест"})
    invalid_id = test_client.post("/api/datasets/not-an-id/analysis", json={"question": "Тест"})
    invalid_question = test_client.post(f"/api/datasets/{uuid4()}/analysis", json={"question": "x"})
    assert unknown.status_code == 404
    assert invalid_id.status_code == 422
    assert invalid_question.status_code == 422


def test_analysis_hides_provider_failure(client):
    test_client, dataset_id = client

    class FailingProvider:
        provider_name = "fake"

        async def analyze_dataset(self, dataset, question, execute_tool=None):
            raise LLMProviderError("secret provider detail")

    app.dependency_overrides[get_llm_provider] = FailingProvider
    response = test_client.post(f"/api/datasets/{dataset_id}/analysis", json={"question": "Тест"})
    assert response.status_code == 502
    assert response.json() == {"detail": "AI-провайдер временно недоступен"}


def test_analysis_requires_configured_provider(client):
    test_client, dataset_id = client
    app.dependency_overrides[get_llm_provider] = lambda: None
    response = test_client.post(f"/api/datasets/{dataset_id}/analysis", json={"question": "Тест"})
    assert response.status_code == 503
    assert response.json() == {"detail": "AI-провайдер не настроен"}
