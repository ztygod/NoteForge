"""LLM 模块的供应商无关数据类型。"""

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias


LLMRole: TypeAlias = Literal["system", "user", "assistant"]
JSONValue: TypeAlias = (
    None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
)


@dataclass(frozen=True, slots=True)
class LLMMessage:
    """发送给模型的一条对话消息。"""

    role: LLMRole
    content: str

    def __post_init__(self) -> None:
        if self.role not in {"system", "user", "assistant"}:
            raise ValueError(f"不支持的消息角色：{self.role}")
        if not isinstance(self.content, str) or not self.content:
            raise ValueError("消息内容不能为空")


@dataclass(frozen=True, slots=True)
class LLMUsage:
    """统一后的 token 用量；供应商未返回时字段为 ``None``。"""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """统一的文本生成结果。"""

    content: str
    model: str
    usage: LLMUsage = field(default_factory=LLMUsage)
    finish_reason: str | None = None
    request_id: str | None = None


@dataclass(frozen=True, slots=True)
class LLMRequestOptions:
    """与供应商无关的常用生成参数。"""

    temperature: float | None = None
    max_tokens: int | None = None

    def __post_init__(self) -> None:
        if self.temperature is not None and self.temperature < 0:
            raise ValueError("temperature 不能小于 0")
        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ValueError("max_tokens 必须大于 0")


RawJSON: TypeAlias = dict[str, Any]
