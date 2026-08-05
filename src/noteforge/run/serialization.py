"""Run 协议使用的稳定 JSON 序列化。"""

from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


def json_value(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {key: json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)
