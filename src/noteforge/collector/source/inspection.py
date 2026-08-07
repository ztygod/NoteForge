"""采集应用层的视频 URL 识别与规范化。"""

from dataclasses import dataclass
from enum import StrEnum
import re
from urllib.parse import parse_qs, urlparse

_BILIBILI_HOSTS = {"bilibili.com", "www.bilibili.com"}
_BVID_PATTERN = re.compile(r"BV[0-9A-Za-z]{10}")
_YOUTUBE_HOSTS = {"m.youtube.com", "music.youtube.com", "www.youtube.com", "youtube.com"}
_YOUTUBE_EMBED_HOSTS = {"www.youtube-nocookie.com", "youtube-nocookie.com"}
_YOUTUBE_SHORT_HOSTS = {"www.youtu.be", "youtu.be"}
_YOUTUBE_VIDEO_ID_PATTERN = re.compile(r"[0-9A-Za-z_-]{11}")


class InspectionPlatform(StrEnum):
    BILIBILI = "bilibili"
    YOUTUBE = "youtube"
    LOCAL = "local"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class InspectionResult:
    original_source: str
    platform: InspectionPlatform
    source_id: str | None = None
    normalized_source: str | None = None
    page_number: int | None = None
    requires_remote_resolution: bool = False


def inspect_source(source: str) -> InspectionResult:
    original = source
    cleaned = source.strip()
    for character in ("?", "=", "&"):
        cleaned = cleaned.replace(f"\\{character}", character)
    parsed = urlparse(cleaned)
    if parsed.scheme in {"http", "https"} and parsed.hostname in _BILIBILI_HOSTS:
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] == "video" and _BVID_PATTERN.fullmatch(parts[1]):
            page = 1
            try:
                page = max(1, int(parse_qs(parsed.query).get("p", ["1"])[0]))
            except ValueError:
                pass
            normalized = f"https://www.bilibili.com/video/{parts[1]}"
            if page != 1:
                normalized += f"?p={page}"
            return InspectionResult(original, InspectionPlatform.BILIBILI, parts[1], normalized, page)

    video_id: str | None = None
    if parsed.scheme in {"http", "https"}:
        parts = [part for part in parsed.path.split("/") if part]
        if parsed.hostname in _YOUTUBE_SHORT_HOSTS and parts:
            video_id = parts[0]
        elif parsed.hostname in _YOUTUBE_HOSTS:
            if parsed.path.rstrip("/") == "/watch":
                video_id = parse_qs(parsed.query).get("v", [None])[0]
            elif len(parts) >= 2 and parts[0] in {"embed", "live", "shorts", "v"}:
                video_id = parts[1]
        elif parsed.hostname in _YOUTUBE_EMBED_HOSTS and len(parts) >= 2 and parts[0] == "embed":
            video_id = parts[1]
    if video_id and _YOUTUBE_VIDEO_ID_PATTERN.fullmatch(video_id):
        return InspectionResult(original, InspectionPlatform.YOUTUBE, video_id, f"https://www.youtube.com/watch?v={video_id}")
    return InspectionResult(original, InspectionPlatform.UNKNOWN)
