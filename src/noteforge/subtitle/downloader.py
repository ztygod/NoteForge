"""使用 yt-dlp Python API 下载选中的字幕文件。"""

from collections.abc import Mapping
from pathlib import Path
import re

import yt_dlp
from yt_dlp.utils import DownloadError

from noteforge.collector.models import SubtitleTrack
from noteforge.collector.ytdlp import build_ytdlp_options
from noteforge.exceptions import (
    InvalidSubtitleResponseError,
    SubtitleDownloadError,
    SubtitleNotFoundError,
)
from noteforge.subtitle.models import SubtitleFile

_UNSAFE_PATH_CHARACTER = re.compile(r"[^0-9A-Za-z._-]+")


def _safe_path_component(value: str) -> str:
    component = _UNSAFE_PATH_CHARACTER.sub("_", value).strip("._")
    return component or "unknown"


class YtDlpSubtitleDownloader:
    """只下载字幕，不下载视频或音频。"""

    def __init__(
        self,
        cookies_from_browser: str | None = "chrome",
        *,
        http_headers: Mapping[str, str] | None = None,
        downloader: yt_dlp.YoutubeDL | None = None,
    ) -> None:
        self._cookies_from_browser = cookies_from_browser
        self._http_headers = http_headers
        self._downloader = downloader

    def download(
        self,
        source: str,
        track: SubtitleTrack,
        *,
        output_dir: Path,
        video_id: str,
        platform: str,
    ) -> SubtitleFile:
        target_dir = (
            output_dir
            / _safe_path_component(platform)
            / _safe_path_component(video_id)
        )
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise SubtitleDownloadError(
                f"无法创建字幕缓存目录：{target_dir}"
            ) from error

        options = build_ytdlp_options(
            self._cookies_from_browser,
            http_headers=self._http_headers,
        )
        options.update(
            {
                # 只请求选择器确定的语言，避免下载无关字幕。
                "subtitleslangs": [track.language],
                # 优先保持选择器确定的格式，缺失时由 yt-dlp 回退。
                "subtitlesformat": f"{track.extension}/best",
                # 字幕文件统一写入已按平台和视频隔离的缓存目录。
                "outtmpl": {
                    "default": str(target_dir / "subtitle.%(ext)s"),
                    "subtitle": str(target_dir / "subtitle.%(ext)s"),
                },
            }
        )

        try:
            info = self._extract_info(source, options)
        except DownloadError as error:
            raise SubtitleDownloadError(
                f"字幕下载失败：{error}"
            ) from error
        except Exception as error:
            raise SubtitleDownloadError("下载字幕时发生未知错误。") from error

        return self._subtitle_file_from_info(info, track)

    def _extract_info(
        self,
        source: str,
        options: dict[str, object],
    ) -> object:
        """使用共享会话或临时会话下载字幕。"""

        if self._downloader is None:
            with yt_dlp.YoutubeDL(options) as downloader:
                return downloader.extract_info(source, download=True)

        # 第一次元数据请求已经触发 Cookie 解密；同一 YoutubeDL 实例的
        # cookiejar 是 cached_property，因此字幕请求不会再次读取浏览器。
        params = self._downloader.params
        missing = object()
        previous = {key: params.get(key, missing) for key in options}
        params.update(options)
        try:
            return self._downloader.extract_info(source, download=True)
        finally:
            for key, value in previous.items():
                if value is missing:
                    params.pop(key, None)
                else:
                    params[key] = value

    @staticmethod
    def _subtitle_file_from_info(
        info: object,
        track: SubtitleTrack,
    ) -> SubtitleFile:
        if not isinstance(info, Mapping):
            raise InvalidSubtitleResponseError("字幕下载结果不是有效的映射。")

        requested_subtitles = info.get("requested_subtitles")
        if not isinstance(requested_subtitles, Mapping):
            raise SubtitleNotFoundError("yt-dlp 未返回已请求的字幕。")

        requested = requested_subtitles.get(track.language)
        if not isinstance(requested, Mapping):
            raise SubtitleNotFoundError(
                f"yt-dlp 未下载所选语言字幕：{track.language}。"
            )

        filepath = requested.get("filepath")
        if not isinstance(filepath, str) or not filepath.strip():
            raise InvalidSubtitleResponseError(
                "yt-dlp 的 requested_subtitles 缺少字幕文件路径。"
            )

        extension = requested.get("ext")
        return SubtitleFile(
            path=Path(filepath),
            language=track.language,
            extension=(
                extension.lower()
                if isinstance(extension, str) and extension
                else track.extension
            ),
            is_automatic=track.is_automatic,
        )
