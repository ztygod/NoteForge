"""采集流程使用的 NoteForge 自有数据模型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping

from noteforge.exceptions import InvalidCollectionResponseError

if TYPE_CHECKING:
    from noteforge.subtitle.models import Transcript


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


@dataclass(frozen=True, slots=True)
class SubtitleTrack:
    """视频平台提供的一种字幕语言和文件格式。"""

    # 字幕语言代码，通常使用平台或 yt-dlp 返回的语言标识。
    # 示例："zh-CN"、"ai-zh"、"en-US"
    language: str

    # 字幕文件扩展名，不包含开头的点。
    # 示例："vtt"、"srt"
    extension: str

    # 字幕资源地址；对于 yt-dlp 返回的内联字幕，使用内部资源引用。
    # 示例："https://example.com/subtitle.vtt"
    # 示例："yt-dlp-inline://ai-zh/srt"
    url: str

    # 字幕轨道的显示名称；来源平台未提供时为 None。
    # 示例："中文（简体）"
    name: str | None = None

    # 是否为平台自动生成的字幕。
    # 示例：B站的 "ai-zh" 字幕为 True，人工上传字幕为 False。
    is_automatic: bool = False


@dataclass(frozen=True, slots=True)
class VideoCollectionResult:
    """视频元数据以及可选的结构化字幕处理结果。"""

    # NoteForge 结构化视频元数据。
    # 示例：VideoMetadata(id="BV1gxgD69E1a", title="测试视频", ...)
    metadata: VideoMetadata

    # 远程采集阶段发现的全部合法字幕轨道；没有字幕时为空元组。
    # 示例：(SubtitleTrack(language="ai-zh", extension="srt", ...),)
    subtitle_tracks: tuple[SubtitleTrack, ...]

    # 根据语言、人工/自动类型和格式优先级选中的字幕轨道。
    # 尚未选择或没有可用字幕时为 None。
    # 示例：SubtitleTrack(language="zh-CN", extension="vtt", ...)
    selected_subtitle: SubtitleTrack | None = None

    # 下载、解析并清洗后的结构化字幕。
    # 未处理字幕、没有字幕或所选格式暂不支持时为 None。
    # 示例：Transcript(language="ai-zh", segments=(...), source="automatic_subtitle")
    transcript: Transcript | None = None
