import base64
import json

import pytest

from app.agent.python_sandbox import PythonSandboxError, execute_python
from app.agent.sandbox_server import reject_unsafe_code
from app.agent.tools import ToolExecutionError, execute_dataset_tool
from app.datasets.models import Dataset


def test_python_sandbox_sends_dataset_content_without_path(tmp_path, monkeypatch):
    source = tmp_path / "sales.csv"
    source.write_text("region,revenue\nNorth,12\n", encoding="utf-8")
    received: dict[str, object] = {}

    def request(payload: bytes) -> bytes:
        received.update(json.loads(payload))
        return b'{"result":{"total":12},"row_count":1,"column_count":2,"execution_ms":3}'

    monkeypatch.setattr("app.agent.python_sandbox._request", request)
    result = execute_python(str(source), {"code": "result = {'total': int(df['revenue'].sum())}"})

    assert result.result == {"total": 12}
    assert "path" not in received
    assert base64.b64decode(received["content_base64"]) == source.read_bytes()


def test_python_sandbox_rejects_invalid_response_and_extra_arguments(tmp_path, monkeypatch):
    source = tmp_path / "sales.csv"
    source.write_text("revenue\n12\n", encoding="utf-8")
    monkeypatch.setattr("app.agent.python_sandbox._request", lambda _: b'{"error":"rejected"}')
    with pytest.raises(PythonSandboxError):
        execute_python(str(source), {"code": "result = 12"})
    with pytest.raises(ToolExecutionError):
        execute_dataset_tool(
            Dataset(storage_path=str(source)),
            "execute_python",
            '{"code":"result = 12", "path":"/etc/passwd"}',
        )


@pytest.mark.parametrize(
    "code",
    [
        "import os\nresult = 1",
        "result = df.__class__",
        "result = pd.read_csv('/etc/passwd')",
        "result = open('/etc/passwd').read()",
    ],
)
def test_python_sandbox_blocks_escape_primitives(code):
    with pytest.raises(ValueError):
        reject_unsafe_code(code)


def test_python_sandbox_allows_dataframe_calculation():
    reject_unsafe_code("result = {'mean': round(float(df['revenue'].mean()), 2)}")
