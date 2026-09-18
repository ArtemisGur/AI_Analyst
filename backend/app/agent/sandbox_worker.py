"""One Python execution inside the sandbox container. It has no filesystem or network authority."""

import base64
import json
import math
import statistics
import sys
import time
from typing import Any

import numpy as np
import pandas as pd

from app.agent.sandbox_server import reject_unsafe_code
from app.datasets.service import parse_dataset

SAFE_BUILTINS = {
    "abs": abs,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}


def json_value(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")
    if isinstance(value, pd.Series):
        return value.to_dict()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main() -> None:
    request = json.loads(sys.stdin.read())
    code = request["code"]
    reject_unsafe_code(code)
    content = base64.b64decode(request["content_base64"], validate=True)
    frame = parse_dataset(content, request["suffix"])
    namespace: dict[str, Any] = {
        "df": frame,
        "pd": pd,
        "np": np,
        "math": math,
        "statistics": statistics,
    }
    started = time.monotonic()
    exec(compile(code, "<analysis>", "exec"), {"__builtins__": SAFE_BUILTINS}, namespace)
    if "result" not in namespace:
        raise ValueError("result is required")
    output = {
        "result": json_value(namespace["result"]),
        "row_count": len(frame),
        "column_count": len(frame.columns),
        "execution_ms": round((time.monotonic() - started) * 1000),
    }
    print(json.dumps(output, ensure_ascii=False, allow_nan=False, default=json_value))


if __name__ == "__main__":
    main()
