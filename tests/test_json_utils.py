"""Tests for safe JSON output helpers."""

from __future__ import annotations

import json
import math

from coinfox.utils.json_utils import safe_json_dumps, safe_json_serialize


class CustomPayload:
    def __init__(self) -> None:
        self.name = "custom"
        self.value = math.inf


def test_safe_json_serialize_normalizes_problem_shapes() -> None:
    payload = {
        None: "none-key",
        "nan": math.nan,
        7: {"nested": [{None: CustomPayload()}]},
        ("tuple", "key"): "tuple-key",
    }

    cleaned = safe_json_serialize(payload)

    assert cleaned["null"] == "none-key"
    assert cleaned["nan"] is None
    assert cleaned["7"]["nested"][0]["null"]["name"] == "custom"
    assert cleaned["7"]["nested"][0]["null"]["value"] is None
    assert cleaned["('tuple', 'key')"] == "tuple-key"


def test_safe_json_dumps_outputs_valid_strict_json() -> None:
    payload = {None: {1: math.inf, "obj": CustomPayload()}}

    text = safe_json_dumps(payload, indent=2, sort_keys=True)
    decoded = json.loads(text)

    assert decoded["null"]["1"] is None
    assert decoded["null"]["obj"]["name"] == "custom"
