"""Safe JSON serialization helpers for CLI and API output."""

from __future__ import annotations

import dataclasses
import json
import math
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any


def safe_json_serialize(obj: Any) -> Any:
    """Recursively prepare an object for strict JSON serialization.

    Dictionary keys are normalized to strings so mixed key types can be sorted.
    Non-finite floats become None, which JSON writes as null.
    """
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return safe_json_serialize(dataclasses.asdict(obj))

    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for key, value in obj.items():
            out[_json_key(key)] = safe_json_serialize(value)
        return out

    if isinstance(obj, (list, tuple, set, frozenset)):
        return [safe_json_serialize(item) for item in obj]

    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None

    if isinstance(obj, (str, int, bool)) or obj is None:
        return obj

    if isinstance(obj, Enum):
        return safe_json_serialize(obj.value)

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    if isinstance(obj, Path):
        return str(obj)

    if hasattr(obj, "__dict__"):
        return safe_json_serialize(vars(obj))

    return str(obj)


def safe_json_dumps(obj: Any, **kwargs: Any) -> str:
    """Dump an object after sanitizing keys and non-JSON values."""
    kwargs.setdefault("allow_nan", False)
    return json.dumps(safe_json_serialize(obj), **kwargs)


def _json_key(key: Any) -> str:
    if key is None:
        return "null"
    if isinstance(key, float) and not math.isfinite(key):
        return "null"
    if isinstance(key, Enum):
        return _json_key(key.value)
    return str(key)
