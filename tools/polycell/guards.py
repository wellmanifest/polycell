"""Process guard grammar: $.object.path == <strict JSON value>."""
from __future__ import annotations

import json
import math
import re


def _invalid_number(value: str):
    raise ValueError(f"non-finite JSON number: {value}")


def _finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        _invalid_number(value)
    return result


def _unique_object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_guard(expression: str) -> tuple[tuple[str, ...], object]:
    if not isinstance(expression, str):
        raise ValueError("expected a string: $.object.path == <JSON value>")
    match = re.fullmatch(r"\s*\$\.(\w+(?:\.\w+)*)\s*==\s*(.+?)\s*", expression, re.DOTALL)
    if not match:
        raise ValueError("expected $.object.path == <JSON value>")
    try:
        expected = json.loads(match[2], parse_constant=_invalid_number,
                              parse_float=_finite_float, object_pairs_hook=_unique_object)
    except (ValueError, RecursionError) as error:
        raise ValueError(f"invalid JSON guard value: {error}") from error
    return tuple(match[1].split(".")), expected


def _json_equal(actual, expected) -> bool:
    # Python considers True == 1, including inside lists and dictionaries.
    if isinstance(expected, bool):
        return isinstance(actual, bool) and actual == expected
    if isinstance(expected, (int, float)):
        return isinstance(actual, (int, float)) and not isinstance(actual, bool) and actual == expected
    if isinstance(expected, list):
        return (isinstance(actual, list) and len(actual) == len(expected)
                and all(_json_equal(a, e) for a, e in zip(actual, expected)))
    if isinstance(expected, dict):
        return (isinstance(actual, dict) and actual.keys() == expected.keys()
                and all(_json_equal(actual[key], value) for key, value in expected.items()))
    return type(actual) is type(expected) and actual == expected


def guard_matches(expression: str, context: dict) -> bool:
    path, expected = parse_guard(expression)
    actual = context
    for key in path:
        if not isinstance(actual, dict) or key not in actual:
            return False
        actual = actual[key]
    return _json_equal(actual, expected)
