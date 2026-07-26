"""Prompt 构建过程中的通用格式化工具。"""

from dataclasses import asdict, is_dataclass
import json
from typing import Any

from noteforge.knowledge.models import KnowledgeChunk


def stringify_prompt_value(value: object) -> str:
    """将变量稳定地转换为可注入 Prompt 的文本。"""

    if isinstance(value, str):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return to_pretty_json(asdict(value))
    if isinstance(value, (dict, list, tuple)):
        return to_pretty_json(value)
    return str(value)


def to_pretty_json(value: object) -> str:
    """输出便于模型阅读且不转义中文的 JSON。"""

    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def format_seconds(value: float) -> str:
    """使用固定精度表示秒数，避免科学计数法影响引用。"""

    return f"{value:.3f}"


def serialize_knowledge_chunk(chunk: KnowledgeChunk) -> str:
    """序列化已有知识块，仅作为 Prompt 输入，不解析模型输出。"""

    return to_pretty_json(asdict(chunk))
