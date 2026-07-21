"""获取视频来源的远端收集结果（元数据）"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CollectionMetadata:
    """视频数据采集结果中的基础元数据"""

    title: str
    uploader: str
    description: str = ""
    duration_seconds: int | None = None
    published_at: datetime | None = None
    cover_url: str | None = None


@dataclass(frozen=True, slots=True)
class CollectionPage:
    """视频中的单个分 P 信息"""

    page_number: int
    cid: int
    title: str
    duration_seconds: int | None = None


@dataclass(frozen=True, slots=True)
class CollectionResult:
    """完整的视频数据采集结果"""

    platform: str
    source_id: str
    source_url: str
    metadata: CollectionMetadata
    pages: tuple[CollectionPage, ...] = field(default_factory=tuple)


def collect_video_data(source_url: str) -> CollectionResult:
    """远端收集视频数据（元数据）"""
    raise NotImplementedError("远端收集视频数据功能尚未实现")
