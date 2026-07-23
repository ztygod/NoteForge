"""使用 yt-dlp 采集 B站视频元数据并转换平台错误。"""

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import yt_dlp
from yt_dlp.utils import DownloadError

from noteforge.collector.base import Collector
from noteforge.collector.models import (
    SubtitleTrack,
    VideoCollectionResult,
    VideoMetadata,
)
from noteforge.collector.ytdlp import build_ytdlp_options
from noteforge.exceptions import (
    CollectionError,
    LoginRequiredError,
    RemoteCollectionError,
    RiskControlError,
    UnsupportedSourceError,
    VideoUnavailableError,
)
from noteforge.subtitle.downloader import YtDlpSubtitleDownloader
from noteforge.subtitle.normalizer import TranscriptNormalizer
from noteforge.subtitle.parser import parse_subtitle
from noteforge.subtitle.selector import (
    DEFAULT_LANGUAGE_PRIORITY,
    SubtitleSelector,
)

# 保留平台结果类型名，实际结构使用统一采集结果。
BilibiliCollectorResult = VideoCollectionResult


def _parse_subtitle_tracks(
    payload: object,
    *,
    is_automatic: bool,
) -> tuple[SubtitleTrack, ...]:
    """容错解析 yt-dlp 的字幕字典，忽略单条异常数据。"""

    if not isinstance(payload, Mapping):
        return ()

    tracks: list[SubtitleTrack] = []
    for language, formats in payload.items():
        if not isinstance(language, str) or not language.strip():
            continue
        if not isinstance(formats, list):
            continue

        for subtitle_format in formats:
            if not isinstance(subtitle_format, Mapping):
                continue
            url = subtitle_format.get("url")
            extension = subtitle_format.get("ext")
            inline_data = subtitle_format.get("data")
            if (
                (not isinstance(url, str) or not url.strip())
                and isinstance(inline_data, str)
                and inline_data
            ):
                # Bilibili 的 AI 字幕由 yt-dlp 转成内联 SRT；只保留不含
                # 正文的内部引用，实际下载仍交给 yt-dlp 再次提取。
                url = f"yt-dlp-inline://{language}/{extension}"
            if (
                not isinstance(url, str)
                or not url.strip()
                or not isinstance(extension, str)
                or not extension.strip()
            ):
                continue
            name = subtitle_format.get("name")
            tracks.append(
                SubtitleTrack(
                    language=language,
                    extension=extension.lower(),
                    url=url,
                    name=name if isinstance(name, str) else None,
                    is_automatic=(
                        is_automatic
                        or language.casefold().startswith("ai-")
                    ),
                )
            )
    return tuple(tracks)


def _collection_result_from_info(
    info: Mapping[str, Any],
) -> VideoCollectionResult:
    metadata = VideoMetadata.from_mapping(info)
    manual_tracks = _parse_subtitle_tracks(
        info.get("subtitles"),
        is_automatic=False,
    )
    automatic_tracks = _parse_subtitle_tracks(
        info.get("automatic_captions"),
        is_automatic=True,
    )
    return VideoCollectionResult(
        metadata=metadata,
        subtitle_tracks=manual_tracks + automatic_tracks,
    )


def _translate_download_error(error: DownloadError) -> CollectionError:
    message = str(error)
    normalized = message.casefold()

    if "unsupported url" in normalized or "no suitable extractor" in normalized:
        return UnsupportedSourceError(f"不支持的视频 URL：{message}")
    if any(
        marker in normalized
        for marker in (
            "login required",
            "sign in",
            "cookies",
            "扫码登录",
            "登录后",
        )
    ):
        return LoginRequiredError(f"该视频需要登录后访问：{message}")
    if (
        "http error 412" in normalized
        or "risk control" in normalized
        or "风控" in message
    ):
        return RiskControlError(
            "视频平台触发访问风控（HTTP 412）；可尝试使用 "
            "--cookies-from-browser 指定已登录的浏览器。"
            f"原始错误：{message}"
        )
    if any(
        marker in normalized
        for marker in (
            "video is unavailable",
            "video unavailable",
            "does not exist",
            "not available",
            "private video",
            "已失效",
            "不存在",
            "不可见",
        )
    ):
        return VideoUnavailableError(f"视频不存在或不可访问：{message}")
    if any(
        marker in normalized
        for marker in ("timed out", "timeout", "connection timeout")
    ):
        return RemoteCollectionError(f"连接视频平台超时：{message}")
    return RemoteCollectionError(f"远程采集视频元数据失败：{message}")


class BilibiliCollector(Collector[VideoCollectionResult]):
    """B站视频信息采集器。"""

    def __init__(self, cookies_from_browser: str | None = "chrome") -> None:
        self._cookies_from_browser = cookies_from_browser

    def collect(self, source: str) -> VideoCollectionResult:
        """采集视频元数据并发现字幕轨道，不下载任何文件。"""

        options = build_ytdlp_options(self._cookies_from_browser)

        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(source, download=False)
        except DownloadError as error:
            raise _translate_download_error(error) from error
        except Exception as error:
            raise RemoteCollectionError("远程采集视频元数据时发生未知错误。") from error

        return _collection_result_from_info(info)


def get_bilibili_video_info(
    source: str,
    *,
    cookies_from_browser: str | None = "chrome",
    include_subtitles: bool = True,
    subtitle_language: str | None = None,
    subtitle_output_dir: Path = Path(".cache/noteforge/subtitles"),
    page_number: int | None = None,
) -> VideoCollectionResult:
    """采集 B站视频信息，并按需完成字幕选择、下载、解析和清洗。"""

    collection = BilibiliCollector(
        cookies_from_browser=cookies_from_browser
    ).collect(source)
    if not include_subtitles:
        return collection

    preferred_languages = DEFAULT_LANGUAGE_PRIORITY
    if subtitle_language:
        preferred_languages = (subtitle_language,) + tuple(
            language
            for language in DEFAULT_LANGUAGE_PRIORITY
            if language.casefold() != subtitle_language.casefold()
        )

    selected_track = SubtitleSelector(
        preferred_languages=preferred_languages
    ).select(collection.subtitle_tracks)
    if selected_track is None:
        return collection
    if selected_track.extension.casefold() not in {"vtt", "srt"}:
        # 仍返回发现和选择结果，避免把“存在但暂不支持解析”的字幕
        # 误报成没有字幕。
        return replace(collection, selected_subtitle=selected_track)

    page_suffix = f"_p{page_number}" if page_number is not None else ""
    subtitle_file = YtDlpSubtitleDownloader(
        cookies_from_browser=cookies_from_browser
    ).download(
        source,
        selected_track,
        output_dir=subtitle_output_dir,
        video_id=f"{collection.metadata.id}{page_suffix}",
        platform="bilibili",
    )
    transcript = TranscriptNormalizer().normalize(
        parse_subtitle(subtitle_file)
    )
    return replace(
        collection,
        selected_subtitle=selected_track,
        transcript=transcript,
    )
