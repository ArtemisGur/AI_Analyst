"""Networkless Unix-socket server for bounded, disposable Python analysis jobs."""

import ast
import base64
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

try:
    import resource
except ImportError:  # pragma: no cover - the server is run only in its Linux container
    resource = None

MAX_REQUEST_BYTES = 30 * 1024 * 1024
MAX_RESULT_BYTES = 64 * 1024
SOCKET_PATH = "/run/ai-analyst/sandbox.sock"
UNSUPPORTED_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.ClassDef,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
)


def reject_unsafe_code(code: str) -> None:
    tree = ast.parse(code, mode="exec")
    forbidden_names = {"__builtins__", "compile", "eval", "exec", "globals", "locals", "open"}
    for node in ast.walk(tree):
        if isinstance(node, UNSUPPORTED_NODES):
            raise ValueError("unsupported syntax")
        if isinstance(node, ast.Name) and (node.id in forbidden_names or node.id.startswith("__")):
            raise ValueError("forbidden name")
        if isinstance(node, ast.Attribute) and (
            node.attr.startswith("_")
            or node.attr.startswith(("read_", "to_"))
            or node.attr in {"ExcelFile", "HDFStore", "load", "save"}
        ):
            raise ValueError("forbidden attribute")


def limit_resources() -> None:
    if resource is None:
        raise RuntimeError("resource limits require Linux")
    resource.setrlimit(resource.RLIMIT_AS, (640 * 1024 * 1024, 640 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (7, 8))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NPROC, (16, 16))


def receive(connection: socket.socket) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = connection.recv(65_536)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_REQUEST_BYTES:
            raise ValueError("request too large")
        chunks.append(chunk)
        if chunk.endswith(b"\n"):
            break
    return b"".join(chunks).rstrip(b"\n")


def handle(payload: bytes) -> bytes:
    request = json.loads(payload)
    code = request["code"]
    if not isinstance(code, str) or len(code) > 6_000:
        raise ValueError("invalid code")
    reject_unsafe_code(code)
    suffix = request["suffix"]
    if suffix not in {".csv", ".xlsx"}:
        raise ValueError("invalid dataset")
    content = base64.b64decode(request["content_base64"], validate=True)
    if len(content) > 20 * 1024 * 1024:
        raise ValueError("dataset too large")
    child_input = json.dumps(
        {"code": code, "suffix": suffix, "content_base64": request["content_base64"]}
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-m", "app.agent.sandbox_worker"],
        input=child_input,
        text=True,
        capture_output=True,
        encoding="utf-8",
        timeout=8,
        preexec_fn=limit_resources,
        env={"PYTHONIOENCODING": "utf-8", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"},
    )
    if completed.returncode or len(completed.stdout.encode("utf-8")) > MAX_RESULT_BYTES:
        raise ValueError("execution rejected")
    result = json.loads(completed.stdout)
    if not isinstance(result, dict) or "error" in result:
        raise ValueError("execution rejected")
    response = json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return response.encode("utf-8")


def main() -> None:
    socket_path = Path(SOCKET_PATH)
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    socket_path.unlink(missing_ok=True)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(socket_path))
        os.chmod(socket_path, 0o666)
        server.listen(4)
        while True:
            connection, _ = server.accept()
            with connection:
                try:
                    response = handle(receive(connection))
                except (ValueError, KeyError, TypeError, UnicodeError, subprocess.TimeoutExpired):
                    response = b'{"error":"rejected"}'
                connection.sendall(response)


if __name__ == "__main__":
    main()
