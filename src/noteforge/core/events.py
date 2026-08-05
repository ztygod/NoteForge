"""供应用层与 CLI 适配器共享的 Pipeline 事件。"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class PipelineStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class PipelineEvent:
    """Pipeline 阶段发送的、与展示方式无关的状态更新。"""

    stage: str
    status: PipelineStatus
    message: str
    progress: float | None = None
    metrics: Mapping[str, Any] = field(default_factory=dict)
    duration: float | None = None

    def __post_init__(self) -> None:
        if not self.stage.strip():
            raise ValueError("Pipeline event stage must not be empty")
        if self.progress is not None and not 0 <= self.progress <= 1:
            raise ValueError("Pipeline event progress must be between 0 and 1")
        if self.duration is not None and self.duration < 0:
            raise ValueError("Pipeline event duration must not be negative")


EventHandler = Callable[[PipelineEvent], None]


def null_event_handler(_: PipelineEvent) -> None:
    """为不需要进度事件的调用方提供默认空处理器。"""


def compose_event_handlers(*handlers: EventHandler) -> EventHandler:
    """将多个事件消费者组合为一个处理器。"""

    def handle(event: PipelineEvent) -> None:
        for handler in handlers:
            handler(event)

    return handle
