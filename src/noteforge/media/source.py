"""媒体 URL 识别与规范化。"""

import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import parse_qs, urlparse

_BVID = re.compile(r"BV[0-9A-Za-z]{10}")
_YOUTUBE_ID = re.compile(r"[0-9A-Za-z_-]{11}")


class InspectionPlatform(StrEnum):
    """URL 本地检查结果；UNKNOWN 不会触发远端解析。"""

    BILIBILI = "bilibili"
    YOUTUBE = "youtube"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class InspectedSource:
    """来源检查结果及其规范化地址。"""

    original_source: str
    platform: InspectionPlatform
    source_id: str | None = None
    normalized_source: str | None = None
    page_number: int | None = None
    requires_remote_resolution: bool = False


def inspect_source(source: str) -> InspectedSource:
    """纯本地识别 Bilibili/YouTube URL，并保留 B 站分 P。"""

    cleaned = source.strip()
    for character in ("?", "=", "&"):
        cleaned = cleaned.replace(f"\\{character}", character)
    parsed = urlparse(cleaned)
    host = (parsed.hostname or "").casefold()
    parts = [part for part in parsed.path.split("/") if part]
    if host in {"bilibili.com", "www.bilibili.com"}:
        if len(parts) >= 2 and parts[0] == "video" and _BVID.fullmatch(parts[1]):
            try:
                page = max(1, int(parse_qs(parsed.query).get("p", ["1"])[0]))
            except ValueError:
                page = 1
            normalized = f"https://www.bilibili.com/video/{parts[1]}"
            if page != 1:
                normalized += f"?p={page}"
            return InspectedSource(
                source,
                InspectionPlatform.BILIBILI,
                parts[1],
                normalized,
                page,
            )
    video_id: str | None = None
    if host in {"youtu.be", "www.youtu.be"} and parts:
        video_id = parts[0]
    elif host in {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
    }:
        if parsed.path.rstrip("/") == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        elif len(parts) >= 2 and parts[0] in {"embed", "live", "shorts", "v"}:
            video_id = parts[1]
    elif host in {"youtube-nocookie.com", "www.youtube-nocookie.com"}:
        if len(parts) >= 2 and parts[0] == "embed":
            video_id = parts[1]
    if video_id and _YOUTUBE_ID.fullmatch(video_id):
        normalized = f"https://www.youtube.com/watch?v={video_id}"
        return InspectedSource(source, InspectionPlatform.YOUTUBE, video_id, normalized)
    return InspectedSource(source, InspectionPlatform.UNKNOWN)


InspectionResult = InspectedSource
