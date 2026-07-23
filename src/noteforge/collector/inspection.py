"""获取视频来源的本地检查结果。

本模块只在本地识别和规范化视频来源，不发送任何网络请求。

不同平台的处理逻辑：

- Bilibili：识别标准视频链接中的 BV 号；读取 ``p`` 查询参数作为分 P，
  未提供或参数无效时默认使用第 1 P；规范链接会移除追踪参数，并在分 P
  大于 1 时保留 ``p`` 参数。
- YouTube：识别 ``watch``、``youtu.be``、``embed``、``shorts``、``live``
  等常见视频链接形式，校验 11 位视频 ID，并统一规范化为标准 ``watch``
  链接；YouTube 没有分 P 概念，因此不设置 ``page_number``。
- 其他来源：返回 ``UNKNOWN``，保留用户的原始输入，不猜测平台或视频 ID。

短链接展开、视频有效性确认和元数据获取需要访问远程服务，不属于本模块职责。
"""

from dataclasses import dataclass
from enum import StrEnum
import re
from urllib.parse import parse_qs, urlparse

_BILIBILI_HOSTS = {"bilibili.com", "www.bilibili.com"}
_BVID_PATTERN = re.compile(r"BV[0-9A-Za-z]{10}")
_YOUTUBE_HOSTS = {
    "m.youtube.com",
    "music.youtube.com",
    "www.youtube.com",
    "youtube.com",
}
_YOUTUBE_EMBED_HOSTS = {
    "www.youtube-nocookie.com",
    "youtube-nocookie.com",
}
_YOUTUBE_SHORT_HOSTS = {"www.youtu.be", "youtu.be"}
_YOUTUBE_VIDEO_ID_PATTERN = re.compile(r"[0-9A-Za-z_-]{11}")


class InspectionPlatform(StrEnum):
    """支持检查的视频来源平台"""

    BILIBILI = "bilibili"
    YOUTUBE = "youtube"
    LOCAL = "local"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class InspectionResult:
    """视频来源的本地检查结果"""

    original_source: str
    platform: InspectionPlatform
    source_id: str | None = None
    normalized_source: str | None = None
    page_number: int | None = None
    requires_remote_resolution: bool = False


def inspect_source(source: str) -> InspectionResult:
    """本地识别视频来源，不执行任何远程请求"""

    original_source = source
    cleaned_source = source.strip()
    for escaped_character in ("?", "=", "&"):
        cleaned_source = cleaned_source.replace(
            f"\\{escaped_character}", escaped_character
        )

    parsed = urlparse(cleaned_source)

    if parsed.scheme in {"http", "https"} and parsed.hostname in _BILIBILI_HOSTS:
        path_parts = [part for part in parsed.path.split("/") if part]

        # 标准视频路径应该类似：
        # /video/BV1CkArz1E4o/
        if len(path_parts) >= 2 and path_parts[0] == "video":
            bvid = path_parts[1]

            if _BVID_PATTERN.fullmatch(bvid):
                query = parse_qs(parsed.query)

                # 在链接没有指定分 P 的情况下，默认分 P 为 1
                page_number = 1
                page_values = query.get("p")

                if page_values:
                    try:
                        parsed_page_number = int(page_values[0])
                        if parsed_page_number >= 1:
                            page_number = parsed_page_number
                    except ValueError:
                        page_number = 1

                normalized_source = f"https://www.bilibili.com/video/{bvid}"
                if page_number != 1:
                    normalized_source = f"{normalized_source}?p={page_number}"

                return InspectionResult(
                    original_source=original_source,
                    platform=InspectionPlatform.BILIBILI,
                    source_id=bvid,
                    normalized_source=normalized_source,
                    page_number=page_number,
                )

    youtube_video_id: str | None = None

    if parsed.scheme in {"http", "https"}:
        if parsed.hostname in _YOUTUBE_SHORT_HOSTS:
            path_parts = [part for part in parsed.path.split("/") if part]
            if path_parts:
                youtube_video_id = path_parts[0]

        elif parsed.hostname in _YOUTUBE_HOSTS:
            path_parts = [part for part in parsed.path.split("/") if part]

            if parsed.path.rstrip("/") == "/watch":
                video_values = parse_qs(parsed.query).get("v")
                if video_values:
                    youtube_video_id = video_values[0]
            elif len(path_parts) >= 2 and path_parts[0] in {
                "embed",
                "live",
                "shorts",
                "v",
            }:
                youtube_video_id = path_parts[1]

        elif parsed.hostname in _YOUTUBE_EMBED_HOSTS:
            path_parts = [part for part in parsed.path.split("/") if part]
            if len(path_parts) >= 2 and path_parts[0] == "embed":
                youtube_video_id = path_parts[1]

    if youtube_video_id and _YOUTUBE_VIDEO_ID_PATTERN.fullmatch(youtube_video_id):
        return InspectionResult(
            original_source=original_source,
            platform=InspectionPlatform.YOUTUBE,
            source_id=youtube_video_id,
            normalized_source=(
                f"https://www.youtube.com/watch?v={youtube_video_id}"
            ),
        )

    # TODO: 未来可以添加对本地文件、腾讯视频等来源的识别逻辑

    return InspectionResult(
        original_source=original_source,
        platform=InspectionPlatform.UNKNOWN,
    )
