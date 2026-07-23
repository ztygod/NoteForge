"""采集流程使用的 NoteForge 自有数据模型。"""

from dataclasses import dataclass
from typing import Any, Mapping

from noteforge.exceptions import InvalidCollectionResponseError


def _required_string(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise InvalidCollectionResponseError(
            f"视频元数据缺少有效的必填字段：{field}。"
        )
    return value


def _optional_string(payload: Mapping[str, Any], field: str) -> str | None:
    value = payload.get(field)
    return value if isinstance(value, str) else None


def _optional_integer(payload: Mapping[str, Any], field: str) -> int | None:
    value = payload.get(field)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    """与具体平台和采集工具解耦的视频元数据。"""

    # 视频在来源平台中的唯一标识。
    # 示例："BV1e3411j7ZM"
    id: str

    # 视频标题。
    # 示例："如何使用 Python 构建一个 Web 应用"
    title: str

    # 视频简介；来源平台未提供时为 None。
    # 示例："本期视频将介绍 FastAPI 的基础用法。"
    description: str | None

    # 视频上传者的显示名称；来源平台未提供时为 None。
    # 示例："NoteForge 学堂"
    uploader: str | None

    # 视频上传者在来源平台中的唯一标识；来源平台未提供时为 None。
    # 示例："354638001"
    uploader_id: str | None

    # 视频时长，单位为秒；来源平台未提供时为 None。
    # 示例：618
    duration: int | None

    # 视频的规范网页地址。
    # 示例："https://www.bilibili.com/video/BV1e3411j7ZM"
    webpage_url: str

    # 视频封面图片地址；来源平台未提供时为 None。
    # 示例："https://i0.hdslb.com/bfs/archive/example.jpg"
    thumbnail: str | None

    # 视频发布日期，格式为 YYYYMMDD；来源平台未提供时为 None。
    # 示例："20240723"
    upload_date: str | None

    # 视频播放次数；来源平台未提供时为 None。
    # 示例：128000
    view_count: int | None

    # 视频点赞次数；来源平台未提供时为 None。
    # 示例：5600
    like_count: int | None

    # yt-dlp 使用的提取器名称；来源平台未提供时为 None。
    # 示例："BiliBili"
    extractor: str | None

    # yt-dlp 提取器的类型标识；来源平台未提供时为 None。
    # 示例："BiliBili"
    extractor_key: str | None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "VideoMetadata":
        """从采集器字典构造模型，并隔离未建模的原始字段。"""

        if not isinstance(payload, Mapping):
            raise InvalidCollectionResponseError("视频平台返回了格式异常的元数据。")

        return cls(
            id=_required_string(payload, "id"),
            title=_required_string(payload, "title"),
            description=_optional_string(payload, "description"),
            uploader=_optional_string(payload, "uploader"),
            uploader_id=_optional_string(payload, "uploader_id"),
            duration=_optional_integer(payload, "duration"),
            webpage_url=_required_string(payload, "webpage_url"),
            thumbnail=_optional_string(payload, "thumbnail"),
            upload_date=_optional_string(payload, "upload_date"),
            view_count=_optional_integer(payload, "view_count"),
            like_count=_optional_integer(payload, "like_count"),
            extractor=_optional_string(payload, "extractor"),
            extractor_key=_optional_string(payload, "extractor_key"),
        )
