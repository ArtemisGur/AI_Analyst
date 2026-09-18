"""Client for the isolated Python analysis container.

The model supplies only code. The backend supplies the selected dataset bytes over a
private Unix socket, so the sandbox never receives a database connection, API key,
or host filesystem mount containing uploads.
"""

import base64
import json
import os
import socket
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SOCKET_PATH = "/run/ai-analyst/sandbox.sock"
REQUEST_TIMEOUT_SECONDS = 12
MAX_CODE_CHARS = 6_000
MAX_DATASET_BYTES = 20 * 1024 * 1024
MAX_RESPONSE_BYTES = 64 * 1024


class PythonArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=MAX_CODE_CHARS)


class PythonResult(BaseModel):
    result: Any
    row_count: int = Field(ge=0)
    column_count: int = Field(ge=0)
    execution_ms: int = Field(ge=0, le=8_000)


PYTHON_TOOL = {
    "type": "function",
    "function": {
        "name": "execute_python",
        "description": (
            "Execute a short Python data-analysis snippet in an isolated container over the FULL "
            "selected CSV/XLSX. The dataframe is named df; pandas is pd, numpy is np, and math and "
            "statistics are available. Do not import modules, access files, make network calls, or "
            "write output. Assign a JSON-serializable value to result. "
            "Use this only for calculations "
            "that need Python, such as custom transformations, regression, or multi-step analysis. "
            "The container has no network, application database, or secrets. It has an 8-second "
            "limit, 640 MiB memory limit, and a 64 KiB result limit."
        ),
        "parameters": PythonArguments.model_json_schema(),
    },
}


class PythonSandboxError(Exception):
    pass


def execute_python(storage_path: str, arguments: dict) -> PythonResult:
    request = PythonArguments.model_validate(arguments)
    try:
        content = Path(storage_path).read_bytes()
    except OSError as error:
        raise PythonSandboxError("Файл датасета недоступен") from error
    if len(content) > MAX_DATASET_BYTES:
        raise PythonSandboxError("Датасет превышает лимит Python-анализа")
    payload = (
        json.dumps(
            {
                "code": request.code,
                "suffix": Path(storage_path).suffix.lower(),
                "content_base64": base64.b64encode(content).decode("ascii"),
            },
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )
    if len(payload) > MAX_DATASET_BYTES * 2:
        raise PythonSandboxError("Датасет превышает лимит Python-анализа")
    try:
        response = _request(payload)
        parsed = json.loads(response)
    except (OSError, TimeoutError, ValueError) as error:
        raise PythonSandboxError("Python-инструмент временно недоступен") from error
    if not isinstance(parsed, dict) or "error" in parsed:
        raise PythonSandboxError("Python-код отклонён или превысил лимиты ресурсов")
    try:
        return PythonResult.model_validate(parsed)
    except ValueError as error:
        raise PythonSandboxError("Python-инструмент вернул некорректный результат") from error


def _request(payload: bytes) -> bytes:
    if os.name == "nt":
        raise OSError("Unix socket is unavailable")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(REQUEST_TIMEOUT_SECONDS)
        client.connect(SOCKET_PATH)
        client.sendall(payload)
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = client.recv(8_192)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise ValueError("response is too large")
            chunks.append(chunk)
        return b"".join(chunks)
