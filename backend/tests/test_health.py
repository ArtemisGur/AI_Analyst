from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_database_status(monkeypatch) -> None:
    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def execute(self, _statement) -> None:
            return None

    monkeypatch.setattr("app.api.health.engine.connect", lambda: Connection())
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}
