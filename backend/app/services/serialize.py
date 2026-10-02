"""Convert engine output (pandas, numpy, sets, paths) into JSON-safe values."""

from __future__ import annotations

import math
from datetime import date, datetime
from pathlib import Path
from typing import Any


def to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(to_jsonable(item) for item in value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)

    try:  # numpy / pandas types, imported lazily
        import numpy as np
        import pandas as pd

        if isinstance(value, pd.DataFrame):
            return records(value)
        if isinstance(value, pd.Series):
            return [to_jsonable(item) for item in value.tolist()]
        if isinstance(value, pd.Timestamp):
            return None if pd.isna(value) else value.isoformat()
        if value is pd.NA or value is pd.NaT:
            return None
        if isinstance(value, np.bool_):
            return bool(value)
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            return to_jsonable(float(value))
        if isinstance(value, np.ndarray):
            return [to_jsonable(item) for item in value.tolist()]
    except ImportError:  # pragma: no cover
        pass

    return str(value)


def records(frame) -> list[dict]:
    """DataFrame -> list of JSON-safe dicts (empty list for None)."""
    if frame is None:
        return []
    try:
        if frame.empty:
            return []
    except AttributeError:
        return to_jsonable(frame)
    return [to_jsonable(row) for row in frame.to_dict("records")]


def number(value: Any, digits: int | None = None) -> float | None:
    value = to_jsonable(value)
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return round(float(value), digits) if digits is not None else float(value)
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return round(parsed, digits) if digits is not None else parsed
