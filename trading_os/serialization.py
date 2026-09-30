from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
import hashlib
import json
from typing import Any


def primitive(value: Any) -> Any:
    if is_dataclass(value):
        return primitive(asdict(value))
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): primitive(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [primitive(v) for v in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(primitive(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
