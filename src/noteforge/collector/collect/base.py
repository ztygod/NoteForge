"""视频信息采集器的公共抽象。"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar


CollectResultT = TypeVar("CollectResultT")


class Collector(ABC, Generic[CollectResultT]):
    """不同视频平台采集器必须实现的统一行为。"""

    @abstractmethod
    def collect(self, source_id: str) -> CollectResultT:
        """根据平台内的视频 ID 采集结构化视频信息。"""

